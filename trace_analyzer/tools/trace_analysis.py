"""Trace analysis utilities for comparing and diffing distributed traces."""

from typing import Any, Dict, List, Optional, Set, Tuple, Union
import json
from datetime import datetime
import time

from ..telemetry import get_tracer, get_meter

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
TraceData = Dict[str, Any]
SpanData = Dict[str, Any]


def calculate_span_durations(trace: str) -> List[SpanData]:
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
        
        try:
            if isinstance(trace, str):
                try:
                    trace = json.loads(trace)
                except json.JSONDecodeError as e:
                    return [{"error": f"Failed to parse trace JSON: {str(e)}"}]

            if not isinstance(trace, dict):
                return [{"error": f"Trace data must be a dictionary, but got {type(trace).__name__}"}]

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
                        start_dt = datetime.fromisoformat(s_start.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(s_end.replace('Z', '+00:00'))
                        duration_ms = (end_dt - start_dt).total_seconds() * 1000
                    except (ValueError, TypeError):
                        # Fallback if timestamp parsing fails
                        pass
                
                timing_info.append({
                    "span_id": s.get("span_id"),
                    "name": s.get("name"),
                    "duration_ms": duration_ms,
                    "start_time": s_start,
                    "end_time": s_end,
                    "parent_span_id": s.get("parent_span_id"),
                    "labels": s.get("labels", {}),
                })
            
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


def extract_errors(trace: str) -> List[Dict[str, Any]]:
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
    start_time = time.time()
    success = True

    with tracer.start_as_current_span("extract_errors") as span:
        span.set_attribute("code.function", "extract_errors")
        
        try:
            if isinstance(trace, str):
                try:
                    trace = json.loads(trace)
                except json.JSONDecodeError as e:
                    return [{"error": f"Failed to parse trace JSON: {str(e)}"}]

            if not isinstance(trace, dict):
                return [{"error": f"Trace data must be a dictionary, but got {type(trace).__name__}"}]

            if "error" in trace:
                return [{"error": trace["error"]}]
            
            spans = trace.get("spans", [])
            errors = []
            
            error_indicators = ["error", "exception", "fault", "failure", "status"]
            
            for s in spans:
                labels = s.get("labels", {})
                span_name = s.get("name", "")
                
                is_error = False
                error_info: Dict[str, Any] = {
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
                    
                    is_http_status = False
                    # Check for HTTP error status codes (4xx, 5xx)
                    if "status" in key_lower or "code" in key_lower:
                        try:
                            code = int(value)
                            is_http_status = True
                            if code >= 400:
                                is_error = True
                                error_info["status_code"] = code
                                error_info["error_type"] = "HTTP Error"
                        except (ValueError, TypeError):
                            pass
                    
                    # Check for explicitly named error/exception labels
                    if any(indicator in key_lower for indicator in error_indicators):
                        # If it was identified as a numeric status code, we rely on the threshold check above
                        if is_http_status and ("status" in key_lower or "code" in key_lower):
                            continue

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


def build_call_graph(trace: str) -> Dict[str, Any]:
    """
    Builds a hierarchical call graph from the trace spans.
    
    This function reconstructs the parent-child relationships to form a tree
    structure, which is useful for structural analysis and visualization.
    
    Args:
        trace: A trace dictionary containing spans.
    
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
        
        try:
            if isinstance(trace, str):
                try:
                    trace = json.loads(trace)
                except json.JSONDecodeError as e:
                    return {"error": f"Failed to parse trace JSON: {str(e)}"}

            if not isinstance(trace, dict):
                return {"error": f"Trace data must be a dictionary, but got {type(trace).__name__}"}

            if "error" in trace:
                return {"error": trace["error"]}
            
            spans = trace.get("spans", [])
            
            # Create lookup maps for O(1) access
            span_by_id = {}
            children_by_parent: Dict[str, List[str]] = {}
            root_spans = []
            span_names: Set[str] = set()
            
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
            
            def build_subtree(span_id: str, depth: int = 0) -> Dict[str, Any]:
                """Recursively builds the tree structure for a given span node."""
                s = span_by_id.get(span_id, {})
                children_ids = children_by_parent.get(span_id, [])
                
                return {
                    "span_id": span_id,
                    "name": s.get("name", "unknown"),
                    "depth": depth,
                    "children": [build_subtree(child_id, depth + 1) for child_id in children_ids],
                    "labels": s.get("labels", {}),
                }
            
            # Build trees starting from all root spans
            span_tree = [build_subtree(root_id) for root_id in root_spans]
            
            # Calculate max depth of the call tree
            def get_max_depth(node: Dict[str, Any]) -> int:
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


def compare_span_timings(
    baseline_trace: str,
    target_trace: str,
) -> Dict[str, Any]:
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
    start_time = time.time()
    success = True
    
    with tracer.start_as_current_span("compare_span_timings") as span:
        span.set_attribute("code.function", "compare_span_timings")
        
        try:
            # calculate_span_durations handles string parsing
            baseline_timings = calculate_span_durations(baseline_trace)
            target_timings = calculate_span_durations(target_trace)
            
            if baseline_timings and isinstance(baseline_timings[0], dict) and "error" in baseline_timings[0]:
                return {"error": f"Baseline trace error: {baseline_timings[0]['error']}"}
            if target_timings and isinstance(target_timings[0], dict) and "error" in target_timings[0]:
                return {"error": f"Target trace error: {target_timings[0]['error']}"}
            
            # Create lookup by span name to compare similar operations
            baseline_by_name: Dict[str, List[SpanData]] = {}
            for s in baseline_timings:
                name = s.get("name")
                if name:
                    if name not in baseline_by_name:
                        baseline_by_name[name] = []
                    baseline_by_name[name].append(s)
            
            target_by_name: Dict[str, List[SpanData]] = {}
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
                    baseline_avg = sum(s.get("duration_ms") or 0 for s in baseline_spans) / len(baseline_spans)
                    target_avg = sum(s.get("duration_ms") or 0 for s in target_spans) / len(target_spans)
                    
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
            
            missing_from_target = [name for name in baseline_by_name if name not in target_by_name]
            new_in_target = [name for name in target_by_name if name not in baseline_by_name]
            
            # Calculate overall stats
            baseline_total = sum(s.get("duration_ms") or 0 for s in baseline_timings)
            target_total = sum(s.get("duration_ms") or 0 for s in target_timings)
            
            result = {
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


def find_structural_differences(
    baseline_trace: str,
    target_trace: str,
) -> Dict[str, Any]:
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
    start_time = time.time()
    success = True
    
    with tracer.start_as_current_span("find_structural_differences") as span:
        span.set_attribute("code.function", "find_structural_differences")
        
        try:
            # build_call_graph handles string parsing
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
            
            result = {
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
