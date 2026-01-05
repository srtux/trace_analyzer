"""Statistical and causal analysis utilities for distributed traces."""

from typing import Any
import math
from collections import defaultdict


def compute_latency_statistics(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Computes comprehensive latency statistics across multiple traces.
    
    Args:
        traces: List of trace dictionaries (from fetch_trace or list results).
    
    Returns:
        Statistical summary including:
        - per_span_stats: Statistics for each unique span name
        - overall_stats: Aggregate statistics across all spans
        - percentiles: P50, P90, P95, P99 latencies
        - anomalies: Spans with unusual latency patterns
    """
    from .trace_analysis import calculate_span_durations
    
    span_durations = defaultdict(list)
    all_durations = []
    
    for trace in traces:
        if "error" in trace:
            continue
        timings = calculate_span_durations(trace)
        for span in timings:
            duration = span.get("duration_ms")
            name = span.get("name")
            if duration is not None and name:
                span_durations[name].append(duration)
                all_durations.append(duration)
    
    if not all_durations:
        return {"error": "No valid duration data found in traces"}
    
    def calc_stats(durations: list[float]) -> dict[str, float]:
        if not durations:
            return {}
        n = len(durations)
        sorted_d = sorted(durations)
        mean = sum(durations) / n
        variance = sum((x - mean) ** 2 for x in durations) / n
        std_dev = math.sqrt(variance)
        
        return {
            "count": n,
            "min": round(sorted_d[0], 2),
            "max": round(sorted_d[-1], 2),
            "mean": round(mean, 2),
            "median": round(sorted_d[n // 2], 2),
            "std_dev": round(std_dev, 2),
            "p50": round(sorted_d[int(n * 0.50)], 2),
            "p90": round(sorted_d[int(n * 0.90)] if n > 1 else sorted_d[0], 2),
            "p95": round(sorted_d[int(n * 0.95)] if n > 1 else sorted_d[0], 2),
            "p99": round(sorted_d[int(n * 0.99)] if n > 1 else sorted_d[0], 2),
            "coefficient_of_variation": round(std_dev / mean * 100, 2) if mean > 0 else 0,
        }
    
    per_span_stats = {
        name: calc_stats(durations) 
        for name, durations in span_durations.items()
    }
    
    # Identify anomalous spans (high coefficient of variation or outliers)
    anomalies = []
    for name, stats in per_span_stats.items():
        cv = stats.get("coefficient_of_variation", 0)
        if cv > 50:  # High variability
            anomalies.append({
                "span_name": name,
                "anomaly_type": "high_variability",
                "coefficient_of_variation": cv,
                "description": f"Span '{name}' has highly variable latency (CV={cv}%)"
            })
        
        # Check for bimodal distribution hint
        durations = span_durations[name]
        if len(durations) >= 10:
            sorted_d = sorted(durations)
            lower_half_mean = sum(sorted_d[:len(sorted_d)//2]) / (len(sorted_d)//2)
            upper_half_mean = sum(sorted_d[len(sorted_d)//2:]) / (len(sorted_d) - len(sorted_d)//2)
            if upper_half_mean > lower_half_mean * 3:
                anomalies.append({
                    "span_name": name,
                    "anomaly_type": "bimodal_distribution",
                    "lower_mean": round(lower_half_mean, 2),
                    "upper_mean": round(upper_half_mean, 2),
                    "description": f"Span '{name}' may have bimodal latency (fast: {lower_half_mean:.0f}ms, slow: {upper_half_mean:.0f}ms)"
                })
    
    return {
        "per_span_stats": per_span_stats,
        "overall_stats": calc_stats(all_durations),
        "total_traces_analyzed": len(traces),
        "unique_span_types": len(per_span_stats),
        "anomalies": anomalies,
    }


def detect_latency_anomalies(
    baseline_traces: list[dict[str, Any]],
    target_trace: dict[str, Any],
    threshold_std_devs: float = 2.0,
) -> dict[str, Any]:
    """
    Detects if spans in the target trace are statistically anomalous compared to baseline.
    
    Uses z-score analysis to identify spans that deviate significantly from baseline patterns.
    
    Args:
        baseline_traces: List of normal/baseline traces to establish patterns.
        target_trace: The trace to analyze for anomalies.
        threshold_std_devs: Number of standard deviations to consider anomalous (default 2.0).
    
    Returns:
        Anomaly detection results with:
        - anomalous_spans: Spans with z-scores exceeding threshold
        - normal_spans: Spans within normal range
        - statistics: Baseline statistics used for comparison
    """
    from .trace_analysis import calculate_span_durations
    
    # Build baseline statistics
    baseline_stats = compute_latency_statistics(baseline_traces)
    if "error" in baseline_stats:
        return {"error": baseline_stats["error"]}
    
    per_span_stats = baseline_stats.get("per_span_stats", {})
    
    # Analyze target trace
    target_timings = calculate_span_durations(target_trace)
    
    anomalous_spans = []
    normal_spans = []
    
    for span in target_timings:
        name = span.get("name")
        duration = span.get("duration_ms")
        
        if not name or duration is None:
            continue
        
        baseline = per_span_stats.get(name)
        if not baseline:
            anomalous_spans.append({
                "span_name": name,
                "duration_ms": duration,
                "anomaly_type": "new_span",
                "z_score": None,
                "description": f"Span '{name}' not seen in baseline traces"
            })
            continue
        
        mean = baseline.get("mean", 0)
        std_dev = baseline.get("std_dev", 1)
        
        if std_dev == 0:
            std_dev = 1  # Avoid division by zero
        
        z_score = (duration - mean) / std_dev
        
        span_result = {
            "span_name": name,
            "duration_ms": round(duration, 2),
            "baseline_mean": mean,
            "baseline_std_dev": std_dev,
            "z_score": round(z_score, 2),
        }
        
        if abs(z_score) > threshold_std_devs:
            span_result["anomaly_type"] = "slow" if z_score > 0 else "fast"
            span_result["severity"] = "high" if abs(z_score) > 3 else "medium"
            span_result["description"] = f"Span '{name}' is {abs(z_score):.1f} std devs {'above' if z_score > 0 else 'below'} baseline"
            anomalous_spans.append(span_result)
        else:
            normal_spans.append(span_result)
    
    # Sort anomalies by z-score magnitude
    anomalous_spans.sort(key=lambda x: abs(x.get("z_score") or 0), reverse=True)
    
    return {
        "anomalous_spans": anomalous_spans,
        "normal_spans": normal_spans,
        "threshold_std_devs": threshold_std_devs,
        "baseline_trace_count": len(baseline_traces),
        "summary": {
            "total_spans_analyzed": len(target_timings),
            "anomalous_count": len(anomalous_spans),
            "normal_count": len(normal_spans),
            "anomaly_rate": round(len(anomalous_spans) / max(len(target_timings), 1) * 100, 1),
        }
    }


def analyze_critical_path(trace: dict[str, Any]) -> dict[str, Any]:
    """
    Identifies the critical path in a trace - the sequence of spans that determined total latency.
    
    Args:
        trace: A trace dictionary containing spans.
    
    Returns:
        Critical path analysis with:
        - critical_path: Ordered list of spans on the critical path
        - total_critical_duration: Sum of critical path durations
        - optimization_opportunities: Spans where optimization would reduce total latency
    """
    from .trace_analysis import calculate_span_durations, build_call_graph
    
    if "error" in trace:
        return {"error": trace["error"]}
    
    timings = calculate_span_durations(trace)
    graph = build_call_graph(trace)
    
    span_by_id = {s.get("span_id"): s for s in timings}
    
    # Find the root span(s) and trace the longest path
    root_spans = graph.get("root_spans", [])
    
    def get_critical_path(span_id: str) -> tuple[float, list[dict]]:
        """Recursively find the critical path from this span."""
        span = span_by_id.get(span_id, {})
        duration = span.get("duration_ms") or 0
        
        # Find children
        children_ids = []
        for tree in graph.get("span_tree", []):
            def find_children(node):
                if node.get("span_id") == span_id:
                    return [c.get("span_id") for c in node.get("children", [])]
                for child in node.get("children", []):
                    result = find_children(child)
                    if result:
                        return result
                return None
            result = find_children(tree)
            if result:
                children_ids = result
                break
        
        if not children_ids:
            return duration, [span]
        
        # Find the child with the longest critical path
        max_child_duration = 0
        max_child_path = []
        for child_id in children_ids:
            child_duration, child_path = get_critical_path(child_id)
            if child_duration > max_child_duration:
                max_child_duration = child_duration
                max_child_path = child_path
        
        return duration + max_child_duration, [span] + max_child_path
    
    # Get critical path from each root
    best_path = []
    best_duration = 0
    for root_id in root_spans:
        duration, path = get_critical_path(root_id)
        if duration > best_duration:
            best_duration = duration
            best_path = path
    
    # Identify optimization opportunities (slowest spans on critical path)
    critical_path_simplified = [
        {
            "span_name": s.get("name"),
            "duration_ms": s.get("duration_ms"),
            "percentage_of_total": round((s.get("duration_ms") or 0) / max(best_duration, 1) * 100, 1),
        }
        for s in best_path if s.get("name")
    ]
    
    optimization_opportunities = sorted(
        [s for s in critical_path_simplified if s["percentage_of_total"] > 10],
        key=lambda x: x["duration_ms"],
        reverse=True
    )[:5]
    
    return {
        "critical_path": critical_path_simplified,
        "total_critical_duration_ms": round(best_duration, 2),
        "path_length": len(critical_path_simplified),
        "optimization_opportunities": optimization_opportunities,
        "summary": f"Critical path has {len(critical_path_simplified)} spans taking {best_duration:.0f}ms total"
    }


def perform_causal_analysis(
    baseline_trace: dict[str, Any],
    target_trace: dict[str, Any],
) -> dict[str, Any]:
    """
    Performs causal analysis to identify the root cause of trace differences.
    
    Uses multiple heuristics to identify what CAUSED the difference:
    - Temporal analysis: Which span slowed down first?
    - Dependency analysis: Do slow spans have common parents?
    - Propagation analysis: Did slowness cascade through the system?
    
    Args:
        baseline_trace: The reference/normal trace.
        target_trace: The trace with issues to analyze.
    
    Returns:
        Causal analysis with:
        - root_cause_candidates: Ranked list of likely root causes
        - propagation_chain: How the issue spread through the system
        - confidence_scores: Confidence in each hypothesis
    """
    from .trace_analysis import (
        calculate_span_durations, 
        compare_span_timings,
        build_call_graph,
    )
    
    timing_diff = compare_span_timings(baseline_trace, target_trace)
    baseline_graph = build_call_graph(baseline_trace)
    target_graph = build_call_graph(target_trace)
    
    slower_spans = timing_diff.get("slower_spans", [])
    
    if not slower_spans:
        return {
            "root_cause_candidates": [],
            "conclusion": "No significant slowdowns detected",
            "confidence": "high"
        }
    
    # Build parent-child relationships for target trace
    parent_map = {}
    def build_parent_map(node, parent_name=None):
        name = node.get("name")
        if name and parent_name:
            parent_map[name] = parent_name
        for child in node.get("children", []):
            build_parent_map(child, name)
    
    for tree in target_graph.get("span_tree", []):
        build_parent_map(tree)
    
    # Analyze each slower span
    root_cause_candidates = []
    
    for slow_span in slower_spans[:10]:  # Top 10 slowest
        span_name = slow_span.get("span_name")
        diff_ms = slow_span.get("diff_ms", 0)
        diff_pct = slow_span.get("diff_percent", 0)
        
        # Check if parent is also slow (propagation) or this is the origin
        parent_name = parent_map.get(span_name)
        parent_is_slow = any(s.get("span_name") == parent_name for s in slower_spans)
        
        candidate = {
            "span_name": span_name,
            "slowdown_ms": diff_ms,
            "slowdown_percent": diff_pct,
            "is_root_cause": not parent_is_slow,
            "parent_span": parent_name,
            "parent_is_slow": parent_is_slow,
        }
        
        # Assign confidence based on magnitude and position
        if not parent_is_slow and diff_pct > 100:
            candidate["confidence"] = "high"
            candidate["hypothesis"] = f"'{span_name}' is likely the root cause - {diff_pct:.0f}% slower with no slow parent"
        elif not parent_is_slow:
            candidate["confidence"] = "medium"
            candidate["hypothesis"] = f"'{span_name}' may be a root cause - independently slow"
        else:
            candidate["confidence"] = "low"
            candidate["hypothesis"] = f"'{span_name}' slowdown likely caused by parent '{parent_name}'"
        
        root_cause_candidates.append(candidate)
    
    # Sort by likelihood (root causes first, then by magnitude)
    root_cause_candidates.sort(
        key=lambda x: (not x["is_root_cause"], -x["slowdown_ms"])
    )
    
    # Build propagation chain
    propagation_chain = []
    for candidate in root_cause_candidates:
        if candidate["is_root_cause"]:
            chain = [candidate["span_name"]]
            # Find children that are also slow
            for other in root_cause_candidates:
                if other.get("parent_span") == candidate["span_name"]:
                    chain.append(other["span_name"])
            if len(chain) > 1:
                propagation_chain.append({
                    "origin": candidate["span_name"],
                    "affected_spans": chain[1:],
                    "description": f"Slowdown in '{candidate['span_name']}' propagated to {len(chain)-1} downstream spans"
                })
    
    # Determine overall conclusion
    high_confidence_causes = [c for c in root_cause_candidates if c["confidence"] == "high"]
    
    if len(high_confidence_causes) == 1:
        conclusion = f"Root cause identified: {high_confidence_causes[0]['hypothesis']}"
        overall_confidence = "high"
    elif len(high_confidence_causes) > 1:
        conclusion = f"Multiple potential root causes: {', '.join(c['span_name'] for c in high_confidence_causes[:3])}"
        overall_confidence = "medium"
    else:
        conclusion = "Root cause unclear - slowdown may be distributed across multiple spans"
        overall_confidence = "low"
    
    return {
        "root_cause_candidates": root_cause_candidates[:5],
        "propagation_chains": propagation_chain,
        "conclusion": conclusion,
        "overall_confidence": overall_confidence,
        "total_slowdown_ms": timing_diff.get("summary", {}).get("total_diff_ms", 0),
    }


def compute_service_level_stats(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Aggregates statistics at the service level based on span naming patterns.
    
    Identifies services from span names (e.g., 'ServiceName/MethodName') and computes
    per-service latency statistics.
    
    Args:
        traces: List of trace dictionaries.
    
    Returns:
        Service-level statistics with:
        - services: Per-service latency stats
        - service_dependencies: Which services call which
        - hotspots: Services contributing most to latency
    """
    from .trace_analysis import calculate_span_durations, build_call_graph
    
    service_durations = defaultdict(list)
    service_calls = defaultdict(lambda: defaultdict(int))
    
    for trace in traces:
        if "error" in trace:
            continue
        
        timings = calculate_span_durations(trace)
        graph = build_call_graph(trace)
        
        for span in timings:
            name = span.get("name", "")
            duration = span.get("duration_ms")
            
            # Extract service name (common patterns: "ServiceName/Method", "service.method", "SERVICE")
            service = name.split("/")[0].split(".")[0].strip()
            if service and duration is not None:
                service_durations[service].append(duration)
        
        # Track service dependencies from call graph
        def track_dependencies(node, parent_service=None):
            name = node.get("name", "")
            service = name.split("/")[0].split(".")[0].strip()
            if parent_service and service and parent_service != service:
                service_calls[parent_service][service] += 1
            for child in node.get("children", []):
                track_dependencies(child, service or parent_service)
        
        for tree in graph.get("span_tree", []):
            track_dependencies(tree)
    
    # Compute per-service stats
    services = {}
    total_time = 0
    
    for service, durations in service_durations.items():
        if not durations:
            continue
        mean = sum(durations) / len(durations)
        services[service] = {
            "call_count": len(durations),
            "total_time_ms": round(sum(durations), 2),
            "mean_ms": round(mean, 2),
            "max_ms": round(max(durations), 2),
            "min_ms": round(min(durations), 2),
        }
        total_time += sum(durations)
    
    # Identify hotspots (services consuming most time)
    hotspots = sorted(
        [
            {
                "service": name,
                "total_time_ms": stats["total_time_ms"],
                "percentage": round(stats["total_time_ms"] / max(total_time, 1) * 100, 1),
            }
            for name, stats in services.items()
        ],
        key=lambda x: x["total_time_ms"],
        reverse=True
    )[:5]
    
    # Format service dependencies
    dependencies = [
        {
            "from_service": caller,
            "to_service": callee,
            "call_count": count
        }
        for caller, callees in service_calls.items()
        for callee, count in callees.items()
    ]
    
    return {
        "services": services,
        "service_dependencies": dependencies,
        "hotspots": hotspots,
        "total_services": len(services),
        "total_time_analyzed_ms": round(total_time, 2),
    }
