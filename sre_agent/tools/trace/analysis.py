"""Trace analysis utilities for span-level analysis."""

import logging
import time
from datetime import datetime
from typing import Any

from ..common import adk_tool
from ..common.telemetry import get_meter, get_tracer, log_tool_call
from .clients import fetch_trace_data

logger = logging.getLogger(__name__)

# Telemetry setup
tracer = get_tracer(__name__)
meter = get_meter(__name__)

# Metrics
execution_duration = meter.create_histogram(
    name="sre_agent.tool.execution_duration",
    description="Duration of tool executions",
    unit="ms",
)
execution_count = meter.create_counter(
    name="sre_agent.tool.execution_count",
    description="Total number of tool calls",
    unit="1",
)
anomalies_detected = meter.create_counter(
    name="sre_agent.analysis.anomalies_detected",
    description="Count of anomalies found",
    unit="1",
)


def _record_telemetry(func_name: str, success: bool = True, duration_ms: float = 0.0):
    attributes = {
        "code.function": func_name,
        "code.namespace": __name__,
        "success": str(success).lower(),
        "sre_agent.tool.name": func_name,
    }
    execution_count.add(1, attributes)
    execution_duration.record(duration_ms, attributes)


# Type aliases
TraceData = dict[str, Any]
SpanData = dict[str, Any]


@adk_tool
def calculate_span_durations(
    trace_id: str, project_id: str | None = None
) -> list[SpanData]:
    """
    Extracts timing information for each span in a trace.

    Args:
        trace_id: The unique trace ID.
        project_id: The Google Cloud Project ID.

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
            span.set_attribute("sre_agent.span_count", len(spans))

            timing_info = []

            for s in spans:
                s_start = s.get("start_time")
                s_end = s.get("end_time")

                duration_ms = None
                if s_start and s_end:
                    try:
                        start_dt = datetime.fromisoformat(
                            s_start.replace("Z", "+00:00")
                        )
                        end_dt = datetime.fromisoformat(s_end.replace("Z", "+00:00"))
                        duration_ms = (end_dt - start_dt).total_seconds() * 1000
                    except (ValueError, TypeError) as e:
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

            # Sort by duration (descending) for easy analysis
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

                for key, value in labels.items():
                    key_lower = key.lower()
                    value_str = str(value).lower() if value else ""

                    # Check HTTP/gRPC status codes first
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
                        except (ValueError, TypeError):
                            pass
                        continue

                    # Check for general status/code fields
                    if "status" in key_lower or "code" in key_lower:
                        try:
                            code = int(value)
                            if code >= 400:
                                is_error = True
                                error_info["status_code"] = code
                                error_info["error_type"] = "http_error"
                        except (ValueError, TypeError):
                            pass
                        continue

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

            span.set_attribute("sre_agent.error_count", len(errors))
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

                # Check clock skew
                if parent_id and parent_id in span_map:
                    parent = span_map[parent_id]
                    p_start_str = parent.get("start_time")
                    p_end_str = parent.get("end_time")

                    if p_start_str and p_end_str:
                        p_start = datetime.fromisoformat(
                            p_start_str.replace("Z", "+00:00")
                        )
                        p_end = datetime.fromisoformat(p_end_str.replace("Z", "+00:00"))

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

            # Create lookup maps
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

            span_tree = [build_subtree(root_id) for root_id in root_spans]

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
            span.set_attribute("sre_agent.max_depth", max_depth)
            span.set_attribute("sre_agent.total_spans", len(spans))
            return result

        except Exception as e:
            span.record_exception(e)
            success = False
            raise e
        finally:
            duration_ms = (time.time() - start_time) * 1000
            _record_telemetry("build_call_graph", success, duration_ms)


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
    errors = []
    if isinstance(trace_data, dict) and "spans" in trace_data:
        for s in trace_data["spans"]:
            if (
                "error" in str(s.get("labels", {})).lower()
                or s.get("labels", {}).get("error") == "true"
            ):
                errors.append({"span_name": s.get("name"), "error": "Detected"})
    else:
        errors = extract_errors(trace_id, project_id)

    # Extract slow spans
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
            except (ValueError, TypeError):
                pass
        spans_with_dur.append({"name": s.get("name"), "duration_ms": dur})

    spans_with_dur.sort(key=lambda x: x["duration_ms"], reverse=True)
    top_slowest = spans_with_dur[:5]

    return {
        "trace_id": trace_data.get("trace_id"),
        "total_spans": len(spans),
        "duration_ms": duration_ms,
        "error_count": len(errors),
        "errors": errors[:5],
        "slowest_spans": top_slowest,
    }
