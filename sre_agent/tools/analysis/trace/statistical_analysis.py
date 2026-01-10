"""Statistical analysis and anomaly detection for trace data."""

import concurrent.futures
import json
import statistics
from collections import defaultdict
from datetime import datetime
from typing import Any

from ...clients.trace import fetch_trace_data
from ...common.decorators import adk_tool
from ...common.telemetry import get_meter, get_tracer

# Telemetry setup
tracer = get_tracer(__name__)
meter = get_meter(__name__)

MAX_WORKERS = 10  # Max concurrent fetches


def _fetch_traces_parallel(
    trace_ids: list[str], project_id: str | None = None, max_traces: int = 50
) -> list[dict[str, Any]]:
    """Fetches multiple traces in parallel."""
    # Cap the number of traces to avoid overwhelming the API
    target_ids = trace_ids[:max_traces]

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        future_to_tid = {
            executor.submit(fetch_trace_data, tid, project_id): tid
            for tid in target_ids
        }

        for future in concurrent.futures.as_completed(future_to_tid):
            try:
                data = future.result()
                if data and "error" not in data:
                    results.append(data)
            except Exception:
                pass

    return results


def compute_latency_statistics(
    trace_ids: list[str], project_id: str | None = None
) -> dict[str, Any]:
    """
    Computes aggregate latency statistics for a list of traces.

    Args:
        trace_ids: List of trace IDs.
        project_id: The Google Cloud Project ID.

    Returns:
        Dictionary containing statistical metrics.
    """
    with tracer.start_as_current_span("compute_latency_statistics"):
        latencies = []
        valid_traces = []

        # Track stats per span name
        span_durations = defaultdict(list)

        # Fetch traces in parallel
        valid_trace_data = _fetch_traces_parallel(trace_ids, project_id)

        for trace_data in valid_trace_data:
            if isinstance(trace_data, dict):
                # Calculate total duration if not present
                duration = trace_data.get("duration_ms")

                # If we have spans, we can also aggregate span-level stats
                if "spans" in trace_data:
                    for s in trace_data["spans"]:
                        # Try to get duration from span
                        d = s.get("duration_ms")
                        if d is None and s.get("start_time") and s.get("end_time"):
                            try:
                                start = datetime.fromisoformat(
                                    s["start_time"].replace("Z", "+00:00")
                                )
                                end = datetime.fromisoformat(
                                    s["end_time"].replace("Z", "+00:00")
                                )
                                d = (end - start).total_seconds() * 1000
                            except Exception:
                                pass

                        if d is not None:
                            span_durations[s.get("name", "unknown")].append(d)

                if duration is not None:
                    latencies.append(float(duration))
                    valid_traces.append(trace_data)

        if not latencies:
            return {"error": "No valid trace durations found"}

        latencies.sort()
        count = len(latencies)

        stats: dict[str, Any] = {
            "count": count,
            "min": latencies[0],
            "max": latencies[-1],
            "mean": statistics.mean(latencies),
            "median": statistics.median(latencies),
            "p90": latencies[int(count * 0.9)] if count > 0 else 0,
            "p95": latencies[int(count * 0.95)] if count > 0 else 0,
            "p99": latencies[int(count * 0.99)] if count > 0 else 0,
        }

        if count > 1:
            stats["stdev"] = statistics.stdev(latencies)
            stats["variance"] = statistics.variance(latencies)
        else:
            stats["stdev"] = 0
            stats["variance"] = 0

        # Calculate per-span stats with Z-score support
        per_span_stats: dict[str, Any] = {}
        for name, durs in span_durations.items():
            if not durs:
                continue
            durs.sort()
            c = len(durs)
            span_mean = statistics.mean(durs)
            per_span_stats[name] = {
                "count": c,
                "mean": span_mean,
                "min": durs[0],
                "max": durs[-1],
                "p95": durs[int(c * 0.95)] if c > 0 else 0,
            }
            # Calculate stdev for Z-score anomaly detection (need at least 2 samples)
            if c > 1:
                per_span_stats[name]["stdev"] = statistics.stdev(durs)
                per_span_stats[name]["variance"] = statistics.variance(durs)
            else:
                per_span_stats[name]["stdev"] = 0
                per_span_stats[name]["variance"] = 0

        stats["per_span_stats"] = per_span_stats

        return stats


def detect_latency_anomalies(
    baseline_trace_ids: list[str],
    target_trace_id: str,
    threshold_sigma: float = 2.0,
    project_id: str | None = None,
) -> dict[str, Any]:
    """
    Detects if the target trace is anomalous compared to baseline distribution using Z-score.
    Also checks individual spans for anomalies if baseline data allows.

    Args:
        baseline_trace_ids: List of normal trace IDs.
        target_trace_id: The trace ID to check.
        threshold_sigma: Number of standard deviations to consider anomalous.
        project_id: The Google Cloud Project ID.

    Returns:
        Anomaly report.
    """
    with tracer.start_as_current_span("detect_latency_anomalies"):
        # Compute baseline stats
        baseline_stats = compute_latency_statistics(baseline_trace_ids, project_id)
        if "error" in baseline_stats:
            return baseline_stats

        mean = baseline_stats["mean"]
        stdev = baseline_stats["stdev"]

        # Get target duration
        target_data = fetch_trace_data(target_trace_id, project_id)
        if not target_data:
            return {"error": "Target trace not found or invalid"}

        target_duration = target_data.get("duration_ms")
        if target_duration is None:
            # Try to calc from spans if needed, or error
            return {"error": "Target trace has no duration_ms"}

        # Z-score calculation for total trace
        if stdev > 0:
            z_score = (target_duration - mean) / stdev
        else:
            # If stdev is 0, any deviation is infinite anomaly, unless equal
            if target_duration == mean:
                z_score = 0
            else:
                # Fallback: if stdev is 0 (all baselines identical), use mean as scale?
                # Or just mark high.
                z_score = 100.0 if target_duration > mean else -100.0

        is_anomaly = abs(z_score) > threshold_sigma

        anomalous_spans = []

        # Check individual spans against baseline per-span stats using Z-score
        if "per_span_stats" in baseline_stats and "spans" in target_data:
            span_stats = baseline_stats["per_span_stats"]
            for s in target_data["spans"]:
                name = s.get("name")
                # Calc duration
                dur = s.get("duration_ms")
                if dur is None and s.get("start_time"):
                    try:
                        start = datetime.fromisoformat(
                            s["start_time"].replace("Z", "+00:00")
                        )
                        end = datetime.fromisoformat(
                            s["end_time"].replace("Z", "+00:00")
                        )
                        dur = (end - start).total_seconds() * 1000
                    except Exception:
                        pass

                if name in span_stats and dur is not None:
                    b_span = span_stats[name]
                    span_mean = b_span.get("mean", 0)
                    span_stdev = b_span.get("stdev", 0)

                    # Calculate Z-score for this span
                    if span_stdev > 0:
                        span_z_score = (dur - span_mean) / span_stdev
                    else:
                        # If stdev is 0, use same logic as trace-level
                        if dur == span_mean:
                            span_z_score = 0
                        else:
                            span_z_score = 100.0 if dur > span_mean else -100.0

                    # Check if anomalous (using same threshold as trace level)
                    if (
                        abs(span_z_score) > threshold_sigma and dur > 50
                    ):  # Ignore tiny spans
                        anomalous_spans.append(
                            {
                                "span_name": name,
                                "duration_ms": dur,
                                "baseline_mean": span_mean,
                                "baseline_stdev": span_stdev,
                                "baseline_p95": b_span["p95"],
                                "z_score": round(span_z_score, 2),
                                "anomaly_type": "slow" if span_z_score > 0 else "fast",
                            }
                        )

        return {
            "is_anomaly": is_anomaly,
            "z_score": z_score,
            "target_duration": target_duration,
            "baseline_mean": mean,
            "baseline_stdev": stdev,
            "threshold_sigma": threshold_sigma,
            "deviation_ms": target_duration - mean,
            "anomalous_spans": anomalous_spans,
        }


def analyze_critical_path(
    trace_id: str, project_id: str | None = None
) -> dict[str, Any]:
    """
    Identifies the critical path of spans in a trace.

    The critical path is calculated by finding the longest path through the span dependency graph.

    Args:
        trace_id: The trace ID to analyze.
        project_id: The Google Cloud Project ID.
    """
    with tracer.start_as_current_span("analyze_critical_path"):
        trace_data = fetch_trace_data(trace_id, project_id)
        if not trace_data:
            return {"error": "Trace not found or invalid"}

        spans = trace_data.get("spans", [])
        if not spans:
            return {"critical_path": []}

        # Parse all spans into a structured format
        parsed_spans = {}
        for s in spans:
            try:
                start = (
                    datetime.fromisoformat(
                        s["start_time"].replace("Z", "+00:00")
                    ).timestamp()
                    * 1000
                )
                end = (
                    datetime.fromisoformat(
                        s["end_time"].replace("Z", "+00:00")
                    ).timestamp()
                    * 1000
                )
                parsed_spans[s["span_id"]] = {
                    "id": s["span_id"],
                    "name": s.get("name"),
                    "start": start,
                    "end": end,
                    "duration": end - start,
                    "parent": s.get("parent_span_id"),
                    "children": [],
                }
            except (ValueError, KeyError):
                continue

        # Build tree (children links)
        root_id = None
        for sid, s in parsed_spans.items():
            if s["parent"] and s["parent"] in parsed_spans:
                parsed_spans[s["parent"]]["children"].append(sid)
            else:
                if (
                    root_id is None
                ):  # Assume first root found is THE root for simplicity
                    root_id = sid

        if not root_id:
            return {"critical_path": []}

        # Enhanced Critical Path Calculation:
        # This algorithm handles both synchronous and asynchronous operations.
        # It calculates the "critical path" as the sequence of spans that determines
        # the minimum possible execution time considering parallelism.
        #
        # Algorithm:
        # 1. For each span, calculate "self time" (time not overlapping with children)
        # 2. Use dynamic programming to find the path with maximum blocking time
        # 3. Account for concurrent children by considering overlap

        def calculate_critical_path_recursive(span_id: str) -> tuple[list[dict], float]:
            """
            Returns (path, blocking_time) where:
            - path: list of span info dicts forming the critical path from this node
            - blocking_time: the actual blocking/critical duration from this span down
            """
            node = parsed_spans[span_id]

            if not node["children"]:
                # Leaf node - its duration is fully critical
                return (
                    [
                        {
                            "name": node["name"],
                            "span_id": node["id"],
                            "duration_ms": node["duration"],
                            "start_ms": node["start"],
                            "end_ms": node["end"],
                            "self_time_ms": node["duration"],
                        }
                    ],
                    node["duration"],
                )

            # Calculate self time (time not overlapping with any child)
            child_coverage = []
            for child_id in node["children"]:
                child = parsed_spans[child_id]
                child_coverage.append((child["start"], child["end"]))

            # Sort and merge overlapping intervals
            if child_coverage:
                child_coverage.sort()
                merged = [child_coverage[0]]
                for start, end in child_coverage[1:]:
                    if start <= merged[-1][1]:
                        # Overlapping - merge
                        merged[-1] = (merged[-1][0], max(merged[-1][1], end))
                    else:
                        merged.append((start, end))

                # Calculate self time
                children_total_time = sum(end - start for start, end in merged)
                self_time = node["duration"] - children_total_time
                self_time = max(0, self_time)  # Can't be negative
            else:
                self_time = node["duration"]

            # Find critical child (the one with longest blocking path)
            max_child_path = None
            max_child_blocking: float = 0.0

            for child_id in node["children"]:
                child_path, child_blocking = calculate_critical_path_recursive(child_id)

                # Check if this child is truly blocking (ends close to parent end)
                child = parsed_spans[child_id]
                gap_to_parent_end = node["end"] - child["end"]

                # If child ends within 5ms of parent, consider it blocking
                # Otherwise, discount its blocking time
                if gap_to_parent_end > 5:
                    # Child finished early - might have been parallel with others
                    # Reduce its effective blocking time
                    effective_blocking = child_blocking * 0.5
                else:
                    effective_blocking = child_blocking

                if effective_blocking > max_child_blocking:
                    max_child_blocking = effective_blocking
                    max_child_path = child_path

            # Build path for this span
            current_span_info = {
                "name": node["name"],
                "span_id": node["id"],
                "duration_ms": node["duration"],
                "start_ms": node["start"],
                "end_ms": node["end"],
                "self_time_ms": self_time,
            }

            total_blocking = self_time + max_child_blocking

            if max_child_path:
                full_path = [current_span_info, *max_child_path]
            else:
                full_path = [current_span_info]

            return (full_path, total_blocking)

        path, total_critical_duration = calculate_critical_path_recursive(root_id)

        # Calculate contribution percentage based on total trace duration
        trace_total_dur = parsed_spans[root_id]["duration"]
        for p in path:
            p["contribution_pct"] = (
                (p["self_time_ms"] / trace_total_dur * 100)
                if trace_total_dur > 0
                else 0
            )
            p["blocking_contribution_pct"] = (
                (p["self_time_ms"] / total_critical_duration * 100)
                if total_critical_duration > 0
                else 0
            )

        # Calculate parallelism metrics
        parallelism_ratio = (
            trace_total_dur / total_critical_duration
            if total_critical_duration > 0
            else 1.0
        )

        return {
            "critical_path": path,
            "total_critical_duration_ms": round(total_critical_duration, 2),
            "trace_duration_ms": round(trace_total_dur, 2),
            "parallelism_ratio": round(parallelism_ratio, 2),
            "parallelism_pct": round((1 - 1 / parallelism_ratio) * 100, 2)
            if parallelism_ratio > 1
            else 0,
        }


@adk_tool
def perform_causal_analysis(
    baseline_trace_id: str, target_trace_id: str, project_id: str | None = None
) -> dict[str, Any] | str:
    """
    Enhanced root cause analysis using span-ID-level precision.
    """
    baseline_data = fetch_trace_data(baseline_trace_id, project_id)
    if not baseline_data or "error" in baseline_data:
        msg = (
            "Invalid baseline_trace JSON"
            if isinstance(baseline_trace_id, str)
            and baseline_trace_id.strip().startswith("{")
            else "Invalid baseline_trace ID provided."
        )
        return json.dumps({"error": msg})

    target_data = fetch_trace_data(target_trace_id, project_id)
    if not target_data or "error" in target_data:
        msg = (
            "Invalid target_trace JSON"
            if isinstance(target_trace_id, str)
            and target_trace_id.strip().startswith("{")
            else "Invalid target_trace ID provided."
        )
        return json.dumps({"error": msg})

    # 1. Build span name mappings for both traces
    baseline_spans_by_name = defaultdict(list)
    for s in baseline_data.get("spans", []):
        baseline_spans_by_name[s.get("name")].append(s)

    target_spans_by_id = {s.get("span_id"): s for s in target_data.get("spans", [])}
    target_spans_by_name = defaultdict(list)
    for s in target_data.get("spans", []):
        target_spans_by_name[s.get("name")].append(s)

    # 2. Analyze Critical Path of target trace to get actual span IDs
    cp_report = analyze_critical_path(target_trace_id, project_id)
    critical_path = cp_report.get("critical_path", [])
    critical_path_ids = {s["span_id"] for s in critical_path}

    # Create map of span_id -> critical path info
    cp_info_map = {s["span_id"]: s for s in critical_path}

    # 3. Build call graph to get depth information
    from .analysis import build_call_graph

    target_graph = build_call_graph(target_trace_id, project_id)

    # Flatten tree to map span_id -> depth
    depth_map = {}

    def traverse(node):
        depth_map[node["span_id"]] = node["depth"]
        for child in node["children"]:
            traverse(child)

    for root in target_graph.get("span_tree", []):
        traverse(root)

    # 4. Calculate detailed timing differences at span-ID level
    candidates = []

    for span_id, target_span in target_spans_by_id.items():
        span_name = target_span.get("name")

        # Get baseline comparison
        baseline_instances = baseline_spans_by_name.get(span_name, [])
        if not baseline_instances:
            continue  # New span, not a slowdown cause

        # Calculate durations
        target_duration = target_span.get("duration_ms")
        if target_duration is None:
            try:
                start = datetime.fromisoformat(
                    target_span["start_time"].replace("Z", "+00:00")
                )
                end = datetime.fromisoformat(
                    target_span["end_time"].replace("Z", "+00:00")
                )
                target_duration = (end - start).total_seconds() * 1000
            except Exception:
                continue

        # Get average baseline duration for this span name
        baseline_durations = []
        for b_span in baseline_instances:
            b_dur = b_span.get("duration_ms")
            if b_dur is None:
                try:
                    start = datetime.fromisoformat(
                        b_span["start_time"].replace("Z", "+00:00")
                    )
                    end = datetime.fromisoformat(
                        b_span["end_time"].replace("Z", "+00:00")
                    )
                    b_dur = (end - start).total_seconds() * 1000
                except Exception:
                    continue
            baseline_durations.append(b_dur)

        if not baseline_durations:
            continue

        baseline_avg = statistics.mean(baseline_durations)
        diff_ms = target_duration - baseline_avg
        diff_percent = (diff_ms / baseline_avg * 100) if baseline_avg > 0 else 0

        # Only consider significantly slower spans
        if diff_ms < 10 and diff_percent < 10:
            continue

        # Check if on critical path
        on_critical_path = span_id in critical_path_ids

        # Get self-time contribution if on critical path
        self_time_contribution = 0
        if on_critical_path and span_id in cp_info_map:
            self_time_contribution = cp_info_map[span_id].get("self_time_ms", 0)

        # Calculate confidence score based on multiple factors
        # Factors:
        # 1. Absolute time difference (higher = more impactful)
        # 2. On critical path (2x multiplier)
        # 3. Self-time contribution (indicates actual work, not just child overhead)
        # 4. Depth (deeper = more likely root cause, diminishing returns after depth 5)

        depth = depth_map.get(span_id, 0)
        depth_factor = min(1.0 + (depth * 0.1), 1.5)  # Max 1.5x boost for depth

        score = diff_ms * depth_factor
        if on_critical_path:
            score *= 2.0
            # Further boost if significant self-time (not just child overhead)
            if self_time_contribution > diff_ms * 0.3:
                score *= 1.3

        candidates.append(
            {
                "span_id": span_id,
                "span_name": span_name,
                "diff_ms": round(diff_ms, 2),
                "diff_percent": round(diff_percent, 1),
                "baseline_avg_ms": round(baseline_avg, 2),
                "target_ms": round(target_duration, 2),
                "on_critical_path": on_critical_path,
                "self_time_ms": round(self_time_contribution, 2)
                if on_critical_path
                else None,
                "depth": depth,
                "confidence_score": round(score, 2),
                "is_likely_root_cause": on_critical_path
                and self_time_contribution > 50,
            }
        )

    # Sort by confidence score
    candidates.sort(key=lambda x: x["confidence_score"], reverse=True)

    # Mark top candidates as probable root causes
    if candidates and candidates[0]["on_critical_path"]:
        candidates[0]["is_likely_root_cause"] = True

    return {
        "root_cause_candidates": candidates[:10],  # Return top 10
        "analysis_method": "span_id_level_critical_path_analysis",
        "total_candidates": len(candidates),
        "critical_path_spans": len(critical_path),
    }


@adk_tool
def analyze_trace_patterns(
    trace_ids: list[str],
    lookback_window_minutes: int = 60,
    project_id: str | None = None,
) -> dict[str, Any]:
    """
    Analyzes patterns across multiple traces to detect trends and recurring issues.

    This function helps identify:
    - Recurring slowdowns (specific spans consistently slow)
    - Intermittent issues (problems that come and go)
    - Degradation trends (performance getting worse over time)
    - Correlation patterns (spans that slow down together)

    Args:
        trace_ids: List of trace IDs to analyze.
        lookback_window_minutes: Time window to consider for trend analysis.
        project_id: The Google Cloud Project ID.

    Returns:
        Dictionary containing pattern analysis results.
    """
    with tracer.start_as_current_span("analyze_trace_patterns"):
        if len(trace_ids) < 3:
            return {"error": "Need at least 3 traces for pattern analysis"}

        # Fetch traces in parallel
        parsed_traces = _fetch_traces_parallel(trace_ids, project_id)

        if len(parsed_traces) < 3:
            return {"error": "Not enough valid traces for pattern analysis"}

        # Track span performance across traces
        span_performance: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "occurrences": 0,
                "durations": [],
                "error_count": 0,
                "traces_with_span": [],
            }
        )

        trace_durations = []
        trace_timestamps = []

        for trace in parsed_traces:
            trace_duration = trace.get("duration_ms", 0)
            trace_durations.append(trace_duration)

            # Extract timestamp if available
            trace_id = trace.get("trace_id", "")
            trace_timestamps.append(trace_id)

            for span in trace.get("spans", []):
                span_name = span.get("name", "unknown")
                duration = span.get("duration_ms")

                if duration is None and span.get("start_time") and span.get("end_time"):
                    try:
                        start = datetime.fromisoformat(
                            span["start_time"].replace("Z", "+00:00")
                        )
                        end = datetime.fromisoformat(
                            span["end_time"].replace("Z", "+00:00")
                        )
                        duration = (end - start).total_seconds() * 1000
                    except Exception:
                        continue

                if duration is not None:
                    perf = span_performance[span_name]
                    perf["occurrences"] += 1
                    perf["durations"].append(duration)
                    perf["traces_with_span"].append(trace_id)

                    # Check for errors
                    labels = span.get("labels", {})
                    if "error" in str(labels).lower():
                        perf["error_count"] += 1

        # Analyze patterns
        recurring_slowdowns = []
        intermittent_issues = []
        high_variance_spans = []

        for span_name, perf in span_performance.items():
            if perf["occurrences"] < 2:
                continue

            durations: list[float] = perf["durations"]  # type: ignore
            mean_dur = statistics.mean(durations)

            if len(durations) > 1:
                stdev_dur = statistics.stdev(durations)
                cv = (
                    stdev_dur / mean_dur if mean_dur > 0 else 0
                )  # Coefficient of variation
            else:
                stdev_dur = 0
                cv = 0

            # Recurring slowdown: consistently slow (low variance, high duration)
            if mean_dur > 100 and cv < 0.3:
                # Find min/max safely
                recurring_slowdowns.append(
                    {
                        "span_name": span_name,
                        "avg_duration_ms": round(mean_dur, 2),
                        "occurrences": perf["occurrences"],
                        "consistency": round((1 - cv) * 100, 1),  # How consistent
                        "pattern_type": "recurring_slowdown",
                    }
                )

            # Intermittent issue: high variance (sometimes fast, sometimes slow)
            if cv > 0.5 and mean_dur > 50:
                intermittent_issues.append(
                    {
                        "span_name": span_name,
                        "avg_duration_ms": round(mean_dur, 2),
                        "stdev_ms": round(stdev_dur, 2),
                        "coefficient_of_variation": round(cv, 2),
                        "min_ms": round(min(durations), 2),
                        "max_ms": round(max(durations), 2),
                        "occurrences": perf["occurrences"],
                        "pattern_type": "intermittent",
                    }
                )

            # High variance spans (unpredictable performance)
            if cv > 0.7 and perf["occurrences"] >= 3:
                high_variance_spans.append(
                    {
                        "span_name": span_name,
                        "coefficient_of_variation": round(cv, 2),
                        "avg_duration_ms": round(mean_dur, 2),
                        "occurrences": perf["occurrences"],
                        "pattern_type": "high_variance",
                    }
                )

        # Sort by impact
        recurring_slowdowns.sort(
            key=lambda x: x["avg_duration_ms"] * x["occurrences"], reverse=True
        )
        intermittent_issues.sort(key=lambda x: x["stdev_ms"], reverse=True)
        high_variance_spans.sort(
            key=lambda x: x["coefficient_of_variation"], reverse=True
        )

        # Analyze overall trace trend
        trend = "stable"
        if len(trace_durations) >= 3:
            # Simple linear trend detection
            first_half_avg = statistics.mean(
                trace_durations[: len(trace_durations) // 2]
            )
            second_half_avg = statistics.mean(
                trace_durations[len(trace_durations) // 2 :]
            )

            change_pct = (
                ((second_half_avg - first_half_avg) / first_half_avg * 100)
                if first_half_avg > 0
                else 0
            )

            if change_pct > 15:
                trend = "degrading"
            elif change_pct < -15:
                trend = "improving"

        return {
            "traces_analyzed": len(parsed_traces),
            "unique_spans": len(span_performance),
            "overall_trend": trend,
            "patterns": {
                "recurring_slowdowns": recurring_slowdowns[:5],
                "intermittent_issues": intermittent_issues[:5],
                "high_variance_spans": high_variance_spans[:5],
            },
            "summary": {
                "total_recurring_slowdowns": len(recurring_slowdowns),
                "total_intermittent_issues": len(intermittent_issues),
                "total_high_variance_spans": len(high_variance_spans),
                "trace_duration_trend": trend,
            },
        }


def compute_service_level_stats(
    trace_ids: list[str], project_id: str | None = None
) -> dict[str, Any]:
    """
    Computes stats aggregated by service name (if available in labels).

    Args:
        trace_ids: List of trace IDs.
        project_id: The Google Cloud Project ID.
    """
    service_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "errors": 0, "total_duration": 0}
    )

    # Fetch traces in parallel
    traces_data = _fetch_traces_parallel(trace_ids, project_id)

    for t_data in traces_data:
        for s in t_data.get("spans", []):
            # Try to find service name in labels, or default to "unknown"
            # Common conventions: service.name, app, component
            labels = s.get("labels", {})
            svc = (
                labels.get("service.name")
                or labels.get("service")
                or labels.get("app")
                or "unknown"
            )

            dur: float = 0.0
            if s.get("start_time") and s.get("end_time"):
                try:
                    start = datetime.fromisoformat(
                        s["start_time"].replace("Z", "+00:00")
                    )
                    end = datetime.fromisoformat(s["end_time"].replace("Z", "+00:00"))
                    dur = (end - start).total_seconds() * 1000
                except Exception:
                    pass

            is_error = "error" in str(labels).lower()

            stats = service_stats[svc]
            stats["count"] += 1
            stats["total_duration"] += dur
            if is_error:
                stats["errors"] += 1

    # Finalize averages
    result = {}
    for svc, stats in service_stats.items():
        if stats["count"] > 0:
            result[svc] = {
                "request_count": stats["count"],
                "error_rate": round(stats["errors"] / stats["count"] * 100, 2),
                "avg_latency": round(stats["total_duration"] / stats["count"], 2),
            }

    return result
