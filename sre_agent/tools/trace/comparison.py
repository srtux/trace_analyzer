"""Trace comparison utilities for diff analysis between traces."""

import logging
import time
from datetime import datetime
from typing import Any

from ..common.telemetry import get_meter, get_tracer, log_tool_call
from ..common import adk_tool
from .analysis import calculate_span_durations, build_call_graph

logger = logging.getLogger(__name__)

# Telemetry setup
tracer = get_tracer(__name__)
meter = get_meter(__name__)

execution_duration = meter.create_histogram(
    name="sre_agent.comparison.execution_duration",
    description="Duration of comparison operations",
    unit="ms",
)
execution_count = meter.create_counter(
    name="sre_agent.comparison.execution_count",
    description="Total number of comparison operations",
    unit="1",
)
anomalies_detected = meter.create_counter(
    name="sre_agent.comparison.anomalies_detected",
    description="Count of differences found",
    unit="1",
)


def _record_telemetry(func_name: str, success: bool = True, duration_ms: float = 0.0):
    attributes = {
        "code.function": func_name,
        "success": str(success).lower(),
    }
    execution_count.add(1, attributes)
    execution_duration.record(duration_ms, attributes)


SpanData = dict[str, Any]


@adk_tool
def compare_span_timings(  # noqa: C901
    baseline_trace_id: str,
    target_trace_id: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """
    Compares timing between spans in two traces and detects performance anti-patterns.

    Args:
        baseline_trace_id: The ID of the reference/normal trace.
        target_trace_id: The ID of the trace being analyzed.
        project_id: The Google Cloud Project ID.

    Returns:
        A comparison report with:
        - slower_spans: Spans that got slower in target
        - faster_spans: Spans that got faster in target
        - missing_from_target: Spans in baseline but not in target
        - new_in_target: Spans in target but not in baseline
        - patterns: Detected anti-patterns (N+1 queries, serial chains)
        - summary: Overall timing comparison summary
    """
    start_time = time.time()
    success = True

    with tracer.start_as_current_span("compare_span_timings") as span:
        span.set_attribute("code.function", "compare_span_timings")

        log_tool_call(
            logger,
            "compare_span_timings",
            baseline_trace_id=baseline_trace_id,
            target_trace_id=target_trace_id,
        )

        try:
            baseline_timings = calculate_span_durations(baseline_trace_id, project_id)
            target_timings = calculate_span_durations(target_trace_id, project_id)

            if (
                baseline_timings
                and isinstance(baseline_timings[0], dict)
                and "error" in baseline_timings[0]
            ):
                return {
                    "error": f"Baseline trace error: {baseline_timings[0]['error']}"
                }
            if (
                target_timings
                and isinstance(target_timings[0], dict)
                and "error" in target_timings[0]
            ):
                return {"error": f"Target trace error: {target_timings[0]['error']}"}

            # Anti-Pattern Detection
            patterns = []

            # N+1 Query Detection
            if target_timings:
                sorted_spans = sorted(
                    [s for s in target_timings if s.get("start_time")],
                    key=lambda x: x["start_time"],
                )

                if sorted_spans:
                    current_run = []
                    for s in sorted_spans:
                        if not current_run:
                            current_run.append(s)
                        else:
                            if s.get("name") == current_run[-1].get("name"):
                                current_run.append(s)
                            else:
                                if len(current_run) >= 3:
                                    duration_sum = sum(
                                        s.get("duration_ms") or 0 for s in current_run
                                    )
                                    if duration_sum > 50:
                                        patterns.append(
                                            {
                                                "type": "n_plus_one",
                                                "description": f"Potential N+1 Query: '{current_run[0].get('name')}' called {len(current_run)} times sequentially.",
                                                "span_name": current_run[0].get("name"),
                                                "count": len(current_run),
                                                "total_duration_ms": duration_sum,
                                                "impact": "high" if duration_sum > 200 else "medium",
                                            }
                                        )
                                current_run = [s]

                    # Check last run
                    if len(current_run) >= 3:
                        duration_sum = sum(
                            s.get("duration_ms") or 0 for s in current_run
                        )
                        if duration_sum > 50:
                            patterns.append(
                                {
                                    "type": "n_plus_one",
                                    "description": f"Potential N+1 Query: '{current_run[0].get('name')}' called {len(current_run)} times sequentially.",
                                    "span_name": current_run[0].get("name"),
                                    "count": len(current_run),
                                    "total_duration_ms": duration_sum,
                                    "impact": "high" if duration_sum > 200 else "medium",
                                }
                            )

            # Serial Chain Detection
            if target_timings and sorted_spans:
                sequential_chains = []
                current_chain = []
                gap_threshold_ms = 10

                for i in range(len(sorted_spans) - 1):
                    curr_span = sorted_spans[i]
                    next_span = sorted_spans[i + 1]

                    if not (curr_span.get("end_time") and next_span.get("start_time")):
                        continue

                    try:
                        curr_end = (
                            datetime.fromisoformat(
                                curr_span["end_time"].replace("Z", "+00:00")
                            ).timestamp()
                            * 1000
                        )
                        next_start = (
                            datetime.fromisoformat(
                                next_span["start_time"].replace("Z", "+00:00")
                            ).timestamp()
                            * 1000
                        )

                        is_parent_child = curr_span.get("span_id") == next_span.get(
                            "parent_span_id"
                        ) or next_span.get("span_id") == curr_span.get("parent_span_id")

                        if is_parent_child:
                            if len(current_chain) >= 3:
                                sequential_chains.append(current_chain[:])
                            current_chain = []
                            continue

                        gap = next_start - curr_end

                        if gap >= 0 and gap <= gap_threshold_ms:
                            if not current_chain:
                                current_chain.append(curr_span)
                            current_chain.append(next_span)
                        else:
                            if len(current_chain) >= 3:
                                sequential_chains.append(current_chain[:])
                            current_chain = []

                    except (ValueError, TypeError, KeyError):
                        continue

                if len(current_chain) >= 3:
                    sequential_chains.append(current_chain[:])

                for chain in sequential_chains:
                    chain_duration = sum(s.get("duration_ms") or 0 for s in chain)

                    if chain_duration > 100:
                        span_names = [s.get("name") for s in chain]
                        patterns.append(
                            {
                                "type": "serial_chain",
                                "description": f"Serial Chain: {len(chain)} operations running sequentially that could potentially be parallelized.",
                                "span_names": span_names,
                                "count": len(chain),
                                "total_duration_ms": round(chain_duration, 2),
                                "impact": "high" if chain_duration > 500 else "medium",
                                "recommendation": "Consider parallelizing these operations using async/await or concurrent execution.",
                            }
                        )

            # Compare spans by name
            baseline_by_name: dict[str, list[SpanData]] = {}
            for s in baseline_timings:
                name = s.get("name")
                if name:
                    if name not in baseline_by_name:
                        baseline_by_name[name] = []
                    baseline_by_name[name].append(s)

            target_by_name: dict[str, list[SpanData]] = {}
            for s in target_timings:
                name = s.get("name")
                if name:
                    if name not in target_by_name:
                        target_by_name[name] = []
                    target_by_name[name].append(s)

            slower_spans = []
            faster_spans = []

            all_names = set(baseline_by_name.keys()) | set(target_by_name.keys())

            for name in all_names:
                baseline_spans = baseline_by_name.get(name, [])
                target_spans = target_by_name.get(name, [])

                if baseline_spans and target_spans:
                    baseline_avg = sum(
                        s.get("duration_ms") or 0 for s in baseline_spans
                    ) / len(baseline_spans)
                    target_avg = sum(
                        s.get("duration_ms") or 0 for s in target_spans
                    ) / len(target_spans)

                    diff_ms = target_avg - baseline_avg
                    diff_pct = (diff_ms / baseline_avg * 100) if baseline_avg > 0 else 0

                    comparison = {
                        "span_name": name,
                        "baseline_duration_ms": round(baseline_avg, 2),
                        "target_duration_ms": round(target_avg, 2),
                        "diff_ms": round(diff_ms, 2),
                        "diff_percent": round(diff_pct, 1),
                        "baseline_count": len(baseline_spans),
                        "target_count": len(target_spans),
                    }

                    if diff_pct > 10 or diff_ms > 50:
                        slower_spans.append(comparison)
                    elif diff_pct < -10 or diff_ms < -50:
                        faster_spans.append(comparison)

            slower_spans.sort(key=lambda x: x["diff_ms"], reverse=True)
            faster_spans.sort(key=lambda x: x["diff_ms"])

            missing_from_target = [
                name for name in baseline_by_name if name not in target_by_name
            ]
            new_in_target = [
                name for name in target_by_name if name not in baseline_by_name
            ]

            baseline_total = sum(s.get("duration_ms") or 0 for s in baseline_timings)
            target_total = sum(s.get("duration_ms") or 0 for s in target_timings)

            result = {
                "slower_spans": slower_spans,
                "faster_spans": faster_spans,
                "missing_from_target": missing_from_target,
                "new_in_target": new_in_target,
                "patterns": patterns,
                "summary": {
                    "baseline_total_ms": round(baseline_total, 2),
                    "target_total_ms": round(target_total, 2),
                    "total_diff_ms": round(target_total - baseline_total, 2),
                    "num_slower": len(slower_spans),
                    "num_faster": len(faster_spans),
                },
            }
            span.set_attribute("sre_agent.slower_spans_count", len(slower_spans))
            anomalies_detected.add(len(slower_spans), {"type": "slow_span"})

            return result
        except Exception as e:
            span.record_exception(e)
            success = False
            raise e
        finally:
            duration_ms = (time.time() - start_time) * 1000
            _record_telemetry("compare_span_timings", success, duration_ms)


@adk_tool
def find_structural_differences(
    baseline_trace_id: str,
    target_trace_id: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """
    Compares the call graph structure between two traces.

    Args:
        baseline_trace_id: The ID of the reference/normal trace.
        target_trace_id: The ID of the trace being analyzed.
        project_id: The Google Cloud Project ID.

    Returns:
        A structural comparison with:
        - missing_spans: Span names present in baseline but not target
        - new_spans: Span names present in target but not baseline
        - depth_change: Change in call tree depth
        - fan_out_changes: Changes in number of child calls
    """
    start_time = time.time()
    success = True

    with tracer.start_as_current_span("find_structural_differences") as span:
        span.set_attribute("code.function", "find_structural_differences")

        log_tool_call(
            logger,
            "find_structural_differences",
            baseline_trace_id=baseline_trace_id,
            target_trace_id=target_trace_id,
        )

        try:
            baseline_graph = build_call_graph(baseline_trace_id, project_id)
            target_graph = build_call_graph(target_trace_id, project_id)

            if "error" in baseline_graph:
                return {"error": f"Baseline trace error: {baseline_graph['error']}"}
            if "error" in target_graph:
                return {"error": f"Target trace error: {target_graph['error']}"}

            baseline_names = set(baseline_graph.get("span_names", []))
            target_names = set(target_graph.get("span_names", []))

            missing_spans = list(baseline_names - target_names)
            new_spans = list(target_names - baseline_names)
            common_spans = list(baseline_names & target_names)

            depth_change = target_graph.get("max_depth", 0) - baseline_graph.get(
                "max_depth", 0
            )

            result = {
                "missing_spans": missing_spans,
                "new_spans": new_spans,
                "common_spans": common_spans,
                "baseline_span_count": baseline_graph.get("total_spans", 0),
                "target_span_count": target_graph.get("total_spans", 0),
                "span_count_change": target_graph.get("total_spans", 0)
                - baseline_graph.get("total_spans", 0),
                "baseline_depth": baseline_graph.get("max_depth", 0),
                "target_depth": target_graph.get("max_depth", 0),
                "depth_change": depth_change,
                "summary": {
                    "spans_removed": len(missing_spans),
                    "spans_added": len(new_spans),
                    "structure_changed": len(missing_spans) > 0
                    or len(new_spans) > 0
                    or depth_change != 0,
                },
            }

            change_count = len(missing_spans) + len(new_spans)
            anomalies_detected.add(change_count, {"type": "structural_change"})
            if depth_change != 0:
                anomalies_detected.add(1, {"type": "depth_change"})

            return result
        except Exception as e:
            span.record_exception(e)
            success = False
            raise e
        finally:
            duration_ms = (time.time() - start_time) * 1000
            _record_telemetry("find_structural_differences", success, duration_ms)
