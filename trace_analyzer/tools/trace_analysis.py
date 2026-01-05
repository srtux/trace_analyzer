"""Trace analysis utilities for comparing and diffing distributed traces."""

from typing import Any
from datetime import datetime


def calculate_span_durations(trace: dict[str, Any]) -> list[dict[str, Any]]:
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
    if "error" in trace:
        return [{"error": trace["error"]}]
    
    spans = trace.get("spans", [])
    timing_info = []
    
    for span in spans:
        start_time = span.get("start_time")
        end_time = span.get("end_time")
        
        duration_ms = None
        if start_time and end_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                duration_ms = (end_dt - start_dt).total_seconds() * 1000
            except (ValueError, TypeError):
                pass
        
        timing_info.append({
            "span_id": span.get("span_id"),
            "name": span.get("name"),
            "duration_ms": duration_ms,
            "start_time": start_time,
            "end_time": end_time,
            "parent_span_id": span.get("parent_span_id"),
            "labels": span.get("labels", {}),
        })
    
    # Sort by duration (descending) for easy analysis of slowest spans
    timing_info.sort(key=lambda x: x.get("duration_ms") or 0, reverse=True)
    
    return timing_info


def extract_errors(trace: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Finds all spans that contain errors or error-related information.
    
    Args:
        trace: A trace dictionary containing spans.
    
    Returns:
        A list of error dictionaries with:
        - span_id: Span identifier
        - span_name: Name of the span with error
        - error_type: Type/category of error
        - error_message: Error message if available
        - status_code: HTTP status code if applicable
        - labels: All labels on the span
    """
    if "error" in trace:
        return [{"error": trace["error"]}]
    
    spans = trace.get("spans", [])
    errors = []
    
    error_indicators = ["error", "exception", "fault", "failure", "status"]
    
    for span in spans:
        labels = span.get("labels", {})
        span_name = span.get("name", "")
        
        is_error = False
        error_info = {
            "span_id": span.get("span_id"),
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
            
            # Check for HTTP error status codes
            if "status" in key_lower or "code" in key_lower:
                try:
                    code = int(value)
                    if code >= 400:
                        is_error = True
                        error_info["status_code"] = code
                        error_info["error_type"] = "HTTP Error"
                except (ValueError, TypeError):
                    pass
            
            # Check for error/exception labels
            if any(indicator in key_lower for indicator in error_indicators):
                if value_str and value_str not in ("false", "0", "none", "ok"):
                    is_error = True
                    error_info["error_type"] = key
                    error_info["error_message"] = str(value)
            
            # Check for gRPC error codes
            if "grpc" in key_lower and "status" in key_lower:
                if value_str not in ("ok", "0"):
                    is_error = True
                    error_info["error_type"] = "gRPC Error"
                    error_info["status_code"] = value
        
        if is_error:
            errors.append(error_info)
    
    return errors


def build_call_graph(trace: dict[str, Any]) -> dict[str, Any]:
    """
    Builds a hierarchical call graph from the trace spans.
    
    Args:
        trace: A trace dictionary containing spans.
    
    Returns:
        A dictionary representing the call graph:
        - root_spans: List of root spans (no parent)
        - span_tree: Nested dictionary of parent-child relationships
        - span_names: Set of unique span names in the trace
        - depth: Maximum depth of the call tree
    """
    if "error" in trace:
        return {"error": trace["error"]}
    
    spans = trace.get("spans", [])
    
    # Create lookup maps
    span_by_id = {}
    children_by_parent = {}
    root_spans = []
    span_names = set()
    
    for span in spans:
        span_id = span.get("span_id")
        parent_id = span.get("parent_span_id")
        span_name = span.get("name", "unknown")
        
        span_by_id[span_id] = span
        span_names.add(span_name)
        
        if parent_id:
            if parent_id not in children_by_parent:
                children_by_parent[parent_id] = []
            children_by_parent[parent_id].append(span_id)
        else:
            root_spans.append(span_id)
    
    def build_subtree(span_id: str, depth: int = 0) -> dict:
        span = span_by_id.get(span_id, {})
        children_ids = children_by_parent.get(span_id, [])
        
        return {
            "span_id": span_id,
            "name": span.get("name", "unknown"),
            "depth": depth,
            "children": [build_subtree(child_id, depth + 1) for child_id in children_ids],
            "labels": span.get("labels", {}),
        }
    
    # Build tree from roots
    span_tree = [build_subtree(root_id) for root_id in root_spans]
    
    # Calculate max depth
    def get_max_depth(node: dict) -> int:
        if not node.get("children"):
            return node.get("depth", 0)
        return max(get_max_depth(child) for child in node["children"])
    
    max_depth = max((get_max_depth(tree) for tree in span_tree), default=0)
    
    return {
        "trace_id": trace.get("trace_id"),
        "root_spans": root_spans,
        "span_tree": span_tree,
        "span_names": list(span_names),
        "total_spans": len(spans),
        "max_depth": max_depth,
    }


def compare_span_timings(
    baseline_trace: dict[str, Any],
    target_trace: dict[str, Any],
) -> dict[str, Any]:
    """
    Compares timing between spans in two traces.
    
    Args:
        baseline_trace: The reference/normal trace to compare against.
        target_trace: The trace being analyzed (potentially slow/abnormal).
    
    Returns:
        A comparison report with:
        - slower_spans: Spans that got slower in target
        - faster_spans: Spans that got faster in target
        - missing_from_target: Spans in baseline but not in target
        - new_in_target: Spans in target but not in baseline
        - summary: Overall timing comparison summary
    """
    baseline_timings = calculate_span_durations(baseline_trace)
    target_timings = calculate_span_durations(target_trace)
    
    # Create lookup by span name
    baseline_by_name = {}
    for span in baseline_timings:
        name = span.get("name")
        if name:
            if name not in baseline_by_name:
                baseline_by_name[name] = []
            baseline_by_name[name].append(span)
    
    target_by_name = {}
    for span in target_timings:
        name = span.get("name")
        if name:
            if name not in target_by_name:
                target_by_name[name] = []
            target_by_name[name].append(span)
    
    slower_spans = []
    faster_spans = []
    
    all_names = set(baseline_by_name.keys()) | set(target_by_name.keys())
    
    for name in all_names:
        baseline_spans = baseline_by_name.get(name, [])
        target_spans = target_by_name.get(name, [])
        
        if baseline_spans and target_spans:
            # Compare average durations
            baseline_avg = sum(s.get("duration_ms") or 0 for s in baseline_spans) / len(baseline_spans)
            target_avg = sum(s.get("duration_ms") or 0 for s in target_spans) / len(target_spans)
            
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
            
            # Consider significant if >10% change or >50ms
            if diff_pct > 10 or diff_ms > 50:
                slower_spans.append(comparison)
            elif diff_pct < -10 or diff_ms < -50:
                faster_spans.append(comparison)
    
    # Sort by magnitude of change
    slower_spans.sort(key=lambda x: x["diff_ms"], reverse=True)
    faster_spans.sort(key=lambda x: x["diff_ms"])
    
    missing_from_target = [name for name in baseline_by_name if name not in target_by_name]
    new_in_target = [name for name in target_by_name if name not in baseline_by_name]
    
    # Calculate overall stats
    baseline_total = sum(s.get("duration_ms") or 0 for s in baseline_timings)
    target_total = sum(s.get("duration_ms") or 0 for s in target_timings)
    
    return {
        "slower_spans": slower_spans,
        "faster_spans": faster_spans,
        "missing_from_target": missing_from_target,
        "new_in_target": new_in_target,
        "summary": {
            "baseline_total_ms": round(baseline_total, 2),
            "target_total_ms": round(target_total, 2),
            "total_diff_ms": round(target_total - baseline_total, 2),
            "num_slower": len(slower_spans),
            "num_faster": len(faster_spans),
        },
    }


def find_structural_differences(
    baseline_trace: dict[str, Any],
    target_trace: dict[str, Any],
) -> dict[str, Any]:
    """
    Compares the call graph structure between two traces.
    
    Args:
        baseline_trace: The reference/normal trace.
        target_trace: The trace being analyzed.
    
    Returns:
        A structural comparison with:
        - missing_spans: Span names present in baseline but not target
        - new_spans: Span names present in target but not baseline
        - depth_change: Change in call tree depth
        - fan_out_changes: Changes in number of child calls
    """
    baseline_graph = build_call_graph(baseline_trace)
    target_graph = build_call_graph(target_trace)
    
    if "error" in baseline_graph:
        return {"error": f"Baseline trace error: {baseline_graph['error']}"}
    if "error" in target_graph:
        return {"error": f"Target trace error: {target_graph['error']}"}
    
    baseline_names = set(baseline_graph.get("span_names", []))
    target_names = set(target_graph.get("span_names", []))
    
    missing_spans = list(baseline_names - target_names)
    new_spans = list(target_names - baseline_names)
    common_spans = list(baseline_names & target_names)
    
    depth_change = target_graph.get("max_depth", 0) - baseline_graph.get("max_depth", 0)
    
    return {
        "missing_spans": missing_spans,
        "new_spans": new_spans,
        "common_spans": common_spans,
        "baseline_span_count": baseline_graph.get("total_spans", 0),
        "target_span_count": target_graph.get("total_spans", 0),
        "span_count_change": target_graph.get("total_spans", 0) - baseline_graph.get("total_spans", 0),
        "baseline_depth": baseline_graph.get("max_depth", 0),
        "target_depth": target_graph.get("max_depth", 0),
        "depth_change": depth_change,
        "summary": {
            "spans_removed": len(missing_spans),
            "spans_added": len(new_spans),
            "structure_changed": len(missing_spans) > 0 or len(new_spans) > 0 or depth_change != 0,
        },
    }
