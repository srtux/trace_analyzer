"""Trace analysis utilities for comparing and diffing distributed traces."""

import logging
import time
from datetime import datetime
from typing import Any

from ..decorators import adk_tool
from ..telemetry import get_meter, get_tracer, log_tool_call
from .o11y_clients import fetch_trace_data

logger = logging.getLogger(__name__)

# Telemetry setup
tracer = get_tracer(__name__)
meter = get_meter(__name__)

# Metrics
execution_duration = meter.create_histogram(
    name="trace_analyzer.tool.execution_duration",
    description="Duration of tool executions",
    unit="ms",
)
execution_count = meter.create_counter(
    name="trace_analyzer.tool.execution_count",
    description="Total number of tool calls",
    unit="1",
)
anomalies_detected = meter.create_counter(
    name="trace_analyzer.analysis.anomalies_detected",
    description="Count of structural differences found",
    unit="1",
)


def _record_telemetry(func_name: str, success: bool = True, duration_ms: float = 0.0):
    attributes = {
        "code.function": func_name,
        "code.namespace": __name__,
        "success": str(success).lower(),
        "trace_analyzer.tool.name": func_name,
    }
    execution_count.add(1, attributes)
    execution_duration.record(duration_ms, attributes)


# Common type aliases
TraceData = dict[str, Any]
SpanData = dict[str, Any]


@adk_tool
def calculate_span_durations(
    trace_id: str, project_id: str | None = None
) -> list[SpanData]:
    """
    Extracts timing information for each span in a trace.

    Args:
        trace: A trace dictionary containing spans (from fetch_trace).

    Returns:
        A list of span timing dictionaries with:
        - span_id: Span identifier
        - name: Span name/operation
        - duration_ms: Duration in milliseconds
        - start_time: ISO format start time
        - end_time: ISO format end time
        - parent_span_id: Parent span ID if any
    """
    start_time = time.time()
    success = True

    with tracer.start_as_current_span("calculate_span_durations") as span:
        span.set_attribute("code.function", "calculate_span_durations")

        log_tool_call(logger, "calculate_span_durations", trace_id=trace_id)

        try:
            trace = fetch_trace_data(trace_id, project_id)
            if "error" in trace:
                span.set_attribute("error", True)
                span.set_status(trace.get("error"))
                return [{"error": trace["error"]}]

            spans = trace.get("spans", [])
            span.set_attribute("trace_analyzer.span_count", len(spans))

            timing_info = []

            for s in spans:
                s_start = s.get("start_time")
                s_end = s.get("end_time")

                duration_ms = None
                if s_start and s_end:
                    try:
                        # Parse ISO timestamps to calculate duration
                        # Note: Handling potentially different timezone formats
                        start_dt = datetime.fromisoformat(
                            s_start.replace("Z", "+00:00")
                        )
                        end_dt = datetime.fromisoformat(s_end.replace("Z", "+00:00"))
                        duration_ms = (end_dt - start_dt).total_seconds() * 1000
                    except (ValueError, TypeError) as e:
                        # Fallback if timestamp parsing fails
                        logger.warning(
                            f"Failed to parse timestamps for span {s.get('span_id')}: {e}"
                        )

                timing_info.append(
                    {
                        "span_id": s.get("span_id"),
                        "name": s.get("name"),
                        "duration_ms": duration_ms,
                        "start_time": s_start,
                        "end_time": s_end,
                        "parent_span_id": s.get("parent_span_id"),
                        "labels": s.get("labels", {}),
                    }
                )

            # Sort by duration (descending) for easy analysis of slowest spans
            timing_info.sort(key=lambda x: x.get("duration_ms") or 0, reverse=True)

            return timing_info

        except Exception as e:
            span.record_exception(e)
            success = False
            raise e
        finally:
            duration_ms = (time.time() - start_time) * 1000
            _record_telemetry("calculate_span_durations", success, duration_ms)


@adk_tool
def extract_errors(  # noqa: C901
    trace_id: str, project_id: str | None = None
) -> list[dict[str, Any]]:
    """
    Finds all spans that contain errors or error-related information.

    Args:
        trace_id: The unique trace ID.
        project_id: The Google Cloud Project ID.

    Returns:
        A list of error dictionaries with:
        - span_id: Span identifier
        - span_name: Name of the span with error
        - error_type: Type/category of error
        - error_message: Error message if available
        - status_code: HTTP status code if applicable
        - labels: All labels on the span
    """
    start_time = time.time()
    success = True

    with tracer.start_as_current_span("extract_errors") as span:
        span.set_attribute("code.function", "extract_errors")

        log_tool_call(logger, "extract_errors", trace_id=trace_id)

        try:
            trace = fetch_trace_data(trace_id, project_id)
            if "error" in trace:
                return [{"error": trace["error"]}]

            spans = trace.get("spans", [])
            errors = []

            # Removed "status" from error_indicators to prevent HTTP 200 false positives
            error_indicators = ["error", "exception", "fault", "failure"]

            for s in spans:
                labels = s.get("labels", {})
                span_name = s.get("name", "")

                is_error = False
                error_info: dict[str, Any] = {
                    "span_id": s.get("span_id"),
                    "span_name": span_name,
                    "error_type": None,
                    "error_message": None,
                    "status_code": None,
                    "labels": labels,
                }

                # Check labels for error indicators
                for key, value in labels.items():
                    key_lower = key.lower()
                    value_str = str(value).lower() if value else ""

                    # CRITICAL: Check HTTP/gRPC status codes FIRST and skip other checks for status fields
                    if (
                        "/http/status_code" in key_lower
                        or "http.status_code" in key_lower
                    ):
                        try:
                            code = int(value)
                            if code >= 400:
                                is_error = True
                                error_info["status_code"] = code
                                error_info["error_type"] = "http_error"
                        except (ValueError, TypeError) as e:
                            logger.warning(
                                f"Failed to parse HTTP status code for span {s.get('span_id')}: {e}"
                            )
                        continue  # Skip other error checks for HTTP status fields

                    # Check for general status/code fields (might be HTTP or other)
                    if "status" in key_lower or "code" in key_lower:
                        try:
                            code = int(value)
                            if code >= 400:
                                is_error = True
                                error_info["status_code"] = code
                                error_info["error_type"] = "http_error"
                        except (ValueError, TypeError):
                            # Don't log here as many fields have "code"/ "status" in name but aren't ints
                            pass
                        continue  # Skip other error checks for status fields

                    # Check for explicitly named error/exception labels
                    if any(indicator in key_lower for indicator in error_indicators):
                        if value_str and value_str not in ("false", "0", "none", "ok"):
                            is_error = True
                            error_info["error_type"] = key
                            error_info["error_message"] = str(value)

                    # Check for gRPC error codes (non-zero is usually error)
                    if "grpc" in key_lower and "status" in key_lower:
                        if value_str not in ("ok", "0"):
                            is_error = True
                            error_info["error_type"] = "gRPC Error"
                            error_info["status_code"] = value

                if is_error:
                    errors.append(error_info)

            span.set_attribute("trace_analyzer.error_count", len(errors))
            anomalies_detected.add(len(errors), {"type": "error_span"})

            return errors
        except Exception as e:
            span.record_exception(e)
            success = False
            raise e
        finally:
            duration_ms = (time.time() - start_time) * 1000
            _record_telemetry("extract_errors", success, duration_ms)


@adk_tool
def validate_trace_quality(  # noqa: C901
    trace_id: str, project_id: str | None = None
) -> dict[str, Any]:
    """
    Validate trace data quality and detect issues.

    Checks for:
    - Orphaned spans (missing parent)
    - Negative durations
    - Clock skew (child span outside parent timespan)
    - Timestamp parsing errors

    Args:
        trace_id: The unique trace ID.
        project_id: The Google Cloud Project ID.

    Returns:
        Dictionary with 'valid' boolean, 'issue_count', and list of 'issues'.
    """
    trace = fetch_trace_data(trace_id, project_id)
    if "error" in trace:
        return {
            "valid": False,
            "issue_count": 1,
            "issues": [{"type": "fetch_error", "message": trace["error"]}],
        }

    spans = trace.get("spans", [])
    issues = []

    # Build parent-child map
    span_map = {s["span_id"]: s for s in spans if "span_id" in s}

    for span in spans:
        span_id = span.get("span_id")
        if not span_id:
            issues.append({"type": "missing_span_id", "message": "Span missing ID"})
            continue

        # Check for orphaned spans
        parent_id = span.get("parent_span_id")
        if parent_id and parent_id not in span_map:
            issues.append(
                {
                    "type": "orphaned_span",
                    "span_id": span_id,
                    "message": f"Parent span {parent_id} not found",
                }
            )

        # Check for negative durations and clock skew
        try:
            start_str = span.get("start_time")
            end_str = span.get("end_time")

            if start_str and end_str:
                start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                duration = (end - start).total_seconds()

                if duration < 0:
                    issues.append(
                        {
                            "type": "negative_duration",
                            "span_id": span_id,
                            "duration_s": duration,
                        }
                    )

                # Check clock skew (child outside parent timespan)
                if parent_id and parent_id in span_map:
                    parent = span_map[parent_id]
                    p_start_str = parent.get("start_time")
                    p_end_str = parent.get("end_time")

                    if p_start_str and p_end_str:
                        p_start = datetime.fromisoformat(
                            p_start_str.replace("Z", "+00:00")
                        )
                        p_end = datetime.fromisoformat(p_end_str.replace("Z", "+00:00"))

                        # Allow some small buffer for clock skew? Strict for now.
                        if start < p_start or end > p_end:
                            issues.append(
                                {
                                    "type": "clock_skew",
                                    "span_id": span_id,
                                    "message": "Child span outside parent timespan",
                                }
                            )
        except (ValueError, TypeError, KeyError) as e:
            issues.append(
                {"type": "timestamp_error", "span_id": span_id, "error": str(e)}
            )

    return {"valid": len(issues) == 0, "issue_count": len(issues), "issues": issues}


@adk_tool
def build_call_graph(trace_id: str, project_id: str | None = None) -> dict[str, Any]:  # noqa: C901
    """
    Builds a hierarchical call graph from the trace spans.

    This function reconstructs the parent-child relationships to form a tree
    structure, which is useful for structural analysis and visualization.

    Args:
        trace_id: The unique trace ID.
        project_id: The Google Cloud Project ID.

    Returns:
        A dictionary representing the call graph:
        - root_spans: List of root spans (no parent)
        - span_tree: Nested dictionary of parent-child relationships
        - span_names: Set of unique span names in the trace
        - depth: Maximum depth of the call tree
    """
    start_time = time.time()
    success = True

    with tracer.start_as_current_span("build_call_graph") as span:
        span.set_attribute("code.function", "build_call_graph")

        log_tool_call(logger, "build_call_graph", trace_id=trace_id)

        try:
            trace = fetch_trace_data(trace_id, project_id)
            if "error" in trace:
                return {"error": trace["error"]}

            spans = trace.get("spans", [])

            # Create lookup maps for O(1) access
            span_by_id = {}
            children_by_parent: dict[str, list[str]] = {}
            root_spans = []
            span_names: set[str] = set()

            for s in spans:
                span_id = s.get("span_id")
                parent_id = s.get("parent_span_id")
                span_name = s.get("name", "unknown")

                if span_id:
                    span_by_id[span_id] = s

                span_names.add(span_name)

                if parent_id:
                    if parent_id not in children_by_parent:
                        children_by_parent[parent_id] = []
                    children_by_parent[parent_id].append(span_id)
                else:
                    root_spans.append(span_id)

            def build_subtree(span_id: str, depth: int = 0) -> dict[str, Any]:
                """Recursively builds the tree structure for a given span node."""
                s = span_by_id.get(span_id, {})
                children_ids = children_by_parent.get(span_id, [])

                return {
                    "span_id": span_id,
                    "name": s.get("name", "unknown"),
                    "depth": depth,
                    "children": [
                        build_subtree(child_id, depth + 1) for child_id in children_ids
                    ],
                    "labels": s.get("labels", {}),
                }

            # Build trees starting from all root spans
            span_tree = [build_subtree(root_id) for root_id in root_spans]

            # Calculate max depth of the call tree
            def get_max_depth(node: dict[str, Any]) -> int:
                if not node.get("children"):
                    return node.get("depth", 0)
                return max(get_max_depth(child) for child in node["children"])

            max_depth = max((get_max_depth(tree) for tree in span_tree), default=0)

            result = {
                "trace_id": trace.get("trace_id"),
                "root_spans": root_spans,
                "span_tree": span_tree,
                "span_names": list(span_names),
                "total_spans": len(spans),
                "max_depth": max_depth,
            }
            span.set_attribute("trace_analyzer.max_depth", max_depth)
            span.set_attribute("trace_analyzer.total_spans", len(spans))
            return result

        except Exception as e:
            span.record_exception(e)
            success = False
            raise e
        finally:
            duration_ms = (time.time() - start_time) * 1000
            _record_telemetry("build_call_graph", success, duration_ms)


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
            # calculate_span_durations handles fetching
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

            # --- Anti-Pattern Detection (Target Trace) ---
            patterns = []

            # 1. N+1 Query Detection
            # Look for sequential spans with identical names
            if target_timings:
                # Sort by start time to analyze sequence
                sorted_spans = sorted(
                    [s for s in target_timings if s.get("start_time")],
                    key=lambda x: x["start_time"],
                )

                if sorted_spans:
                    current_run = []
                    for _i, s in enumerate(sorted_spans):
                        name = s.get("name")
                        # Skip small utility spans if necessary, but finding all repeats is good
                        if not current_run:
                            current_run.append(s)
                        else:
                            if s.get("name") == current_run[-1].get("name"):
                                current_run.append(s)
                            else:
                                # Run ended
                                if (
                                    len(current_run) >= 3
                                ):  # Threshold: at least 3 repeats
                                    duration_sum = sum(
                                        s.get("duration_ms") or 0 for s in current_run
                                    )
                                    if duration_sum > 50:  # Threshold: >50ms impact
                                        patterns.append(
                                            {
                                                "type": "n_plus_one",
                                                "description": f"Potential N+1 Query: '{current_run[0].get('name')}' called {len(current_run)} times sequentially.",
                                                "span_name": current_run[0].get("name"),
                                                "count": len(current_run),
                                                "total_duration_ms": duration_sum,
                                                "impact": "high"
                                                if duration_sum > 200
                                                else "medium",
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
                                    "impact": "high"
                                    if duration_sum > 200
                                    else "medium",
                                }
                            )

            # 2. Serial Chain Detection
            # Identify waterfall patterns where End(span_N) ≈ Start(span_N+1)
            if target_timings and sorted_spans:
                # Find chains where spans are sequential but not nested
                # This indicates operations that COULD run in parallel but don't
                sequential_chains = []
                current_chain = []

                # Gap threshold: if gap < 10ms, consider it sequential
                # (accounts for small network/processing delays)
                gap_threshold_ms = 10

                for i in range(len(sorted_spans) - 1):
                    curr_span = sorted_spans[i]
                    next_span = sorted_spans[i + 1]

                    # Skip if we don't have timing info
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

                        # Check if they're NOT parent-child (that's expected nesting)
                        is_parent_child = curr_span.get("span_id") == next_span.get(
                            "parent_span_id"
                        ) or next_span.get("span_id") == curr_span.get("parent_span_id")

                        if is_parent_child:
                            # Reset chain if we hit nested spans
                            if len(current_chain) >= 3:
                                sequential_chains.append(current_chain[:])
                            current_chain = []
                            continue

                        # Calculate gap
                        gap = next_start - curr_end

                        if gap >= 0 and gap <= gap_threshold_ms:
                            # Sequential! Add to chain
                            if not current_chain:
                                current_chain.append(curr_span)
                            current_chain.append(next_span)
                        else:
                            # Chain broken
                            if len(current_chain) >= 3:
                                sequential_chains.append(current_chain[:])
                            current_chain = []

                    except (ValueError, TypeError, KeyError):
                        continue

                # Check last chain
                if len(current_chain) >= 3:
                    sequential_chains.append(current_chain[:])

                # Report significant chains
                for chain in sequential_chains:
                    chain_duration = sum(s.get("duration_ms") or 0 for s in chain)

                    # Only report if significant impact (>100ms total)
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

            # --- End Detection ---

            # Create lookup by span name to compare similar operations
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
                    # Compare average durations (handling multiple spans of same name)
                    baseline_avg = sum(
                        s.get("duration_ms") or 0 for s in baseline_spans
                    ) / len(baseline_spans)
                    target_avg = sum(
                        s.get("duration_ms") or 0 for s in target_spans
                    ) / len(target_spans)

                    diff_ms = target_avg - baseline_avg
                    # Calculate percentage change
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

                    # Thresholds for significance: >10% change OR >50ms absolute difference
                    if diff_pct > 10 or diff_ms > 50:
                        slower_spans.append(comparison)
                    elif diff_pct < -10 or diff_ms < -50:
                        faster_spans.append(comparison)

            # Sort by magnitude of change (absolute impact)
            slower_spans.sort(key=lambda x: x["diff_ms"], reverse=True)
            faster_spans.sort(key=lambda x: x["diff_ms"])

            missing_from_target = [
                name for name in baseline_by_name if name not in target_by_name
            ]
            new_in_target = [
                name for name in target_by_name if name not in baseline_by_name
            ]

            # Calculate overall stats
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
            span.set_attribute("trace_analyzer.slower_spans_count", len(slower_spans))
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
def summarize_trace(trace_id: str, project_id: str | None = None) -> dict[str, Any]:
    """
    Creates a summary of a trace to save context window tokens.
    Extracts high-level stats, top 5 slowest spans, and error spans.

    Args:
        trace_id: The unique trace ID.
        project_id: The Google Cloud Project ID.
    """
    log_tool_call(logger, "summarize_trace", trace_id=trace_id)

    trace_data = fetch_trace_data(trace_id, project_id)
    if "error" in trace_data:
        return trace_data

    spans = trace_data.get("spans", [])
    duration_ms = trace_data.get("duration_ms", 0)

    # Extract errors
    # Note: we can't easily reuse extract_errors here without circular deps or redundant parsing if passed a dict
    # but since extract_errors takes str/dict, it's fine.
    # However, to avoid double parsing, let's just do a quick scan if it's a dict

    errors = []
    if isinstance(trace_data, dict) and "spans" in trace_data:
        # Quick extract to avoid overhead
        for s in trace_data["spans"]:
            if (
                "error" in str(s.get("labels", {})).lower()
                or s.get("labels", {}).get("error") == "true"
            ):
                errors.append({"span_name": s.get("name"), "error": "Detected"})
    else:
        errors = extract_errors(trace_id, project_id)  # Fallback to full tool

    # Extract slow spans
    # Sort spans by duration if available, else calc
    spans_with_dur = []
    for s in spans:
        dur = 0
        if "duration_ms" in s:
            dur = s["duration_ms"]
        elif s.get("start_time") and s.get("end_time"):
            try:
                start = datetime.fromisoformat(s["start_time"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(s["end_time"].replace("Z", "+00:00"))
                dur = (end - start).total_seconds() * 1000
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Failed to parse timestamps for span {s.get('name')} in summarize_trace: {e}"
                )
        spans_with_dur.append({"name": s.get("name"), "duration_ms": dur})

    spans_with_dur.sort(key=lambda x: x["duration_ms"], reverse=True)
    top_slowest = spans_with_dur[:5]

    return {
        "trace_id": trace_data.get("trace_id"),
        "total_spans": len(spans),
        "duration_ms": duration_ms,
        "error_count": len(errors),
        "errors": errors[:5],  # Limit errors
        "slowest_spans": top_slowest,
    }


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
            # build_call_graph handles fetching
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
