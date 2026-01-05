"""Cloud Trace API client tools for fetching and querying traces."""

import os
import logging
from typing import Any
from datetime import datetime, timedelta, timezone

from google.cloud import trace_v1

logger = logging.getLogger(__name__)


def _get_trace_client() -> trace_v1.TraceServiceClient:
    """Create and return a Cloud Trace client."""
    return trace_v1.TraceServiceClient()


def _get_project_id() -> str:
    """Get the GCP project ID from environment."""
    project_id = os.environ.get("TRACE_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT or TRACE_PROJECT_ID environment variable must be set")
    return project_id


def fetch_trace(project_id: str, trace_id: str) -> dict[str, Any]:
    """
    Fetches a complete trace with all its spans from Cloud Trace.
    
    Args:
        project_id: The GCP project ID where the trace is stored.
        trace_id: The unique trace ID (32-character hex string).
    
    Returns:
        A dictionary containing the trace data with all spans, including:
        - trace_id: The trace identifier
        - project_id: The project ID
        - spans: List of span dictionaries with timing and metadata
    """
    try:
        client = _get_trace_client()
        trace = client.get_trace(project_id=project_id, trace_id=trace_id)
        
        spans = []
        for span in trace.spans:
            span_data = {
                "span_id": span.span_id,
                "name": span.name,
                "parent_span_id": span.parent_span_id if span.parent_span_id else None,
                "start_time": span.start_time.isoformat() if span.start_time else None,
                "end_time": span.end_time.isoformat() if span.end_time else None,
                "kind": str(span.kind) if span.kind else None,
                "labels": dict(span.labels) if span.labels else {},
            }
            spans.append(span_data)
        
        return {
            "trace_id": trace.trace_id,
            "project_id": trace.project_id,
            "spans": spans,
            "span_count": len(spans),
        }
    except Exception as e:
        logger.error(f"Error fetching trace {trace_id}: {e}")
        return {"error": str(e), "trace_id": trace_id}


def list_traces(
    project_id: str,
    filter_str: str = "",
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 20,
    order_by: str = "start_time desc",
) -> list[dict[str, Any]]:
    """
    Lists traces matching the specified filter criteria.
    
    Args:
        project_id: The GCP project ID to query traces from.
        filter_str: Cloud Trace filter string (e.g., 'span:my-service' or 'latency:>1s').
        start_time: ISO format start time for the query window. Defaults to 1 hour ago.
        end_time: ISO format end time for the query window. Defaults to now.
        limit: Maximum number of traces to return (default 20).
        order_by: Sort order ('start_time desc', 'duration desc', etc.).
    
    Returns:
        A list of trace summary dictionaries containing trace_id and basic info.
    """
    try:
        client = _get_trace_client()
        
        # Default time range: last hour
        now = datetime.now(timezone.utc)
        if end_time:
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        else:
            end_dt = now
            
        if start_time:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        else:
            start_dt = now - timedelta(hours=1)
        
        request = trace_v1.ListTracesRequest(
            project_id=project_id,
            filter=filter_str,
            start_time=start_dt,
            end_time=end_dt,
            order_by=order_by,
            page_size=limit,
        )
        
        traces = []
        response = client.list_traces(request=request)
        
        for trace in response:
            if len(traces) >= limit:
                break
            trace_summary = {
                "trace_id": trace.trace_id,
                "project_id": trace.project_id,
                "span_count": len(trace.spans) if trace.spans else 0,
            }
            traces.append(trace_summary)
        
        return traces
    except Exception as e:
        logger.error(f"Error listing traces: {e}")
        return [{"error": str(e)}]


def find_example_traces(
    project_id: str | None = None,
    service_filter: str = "",
    time_window_hours: int = 24,
) -> dict[str, Any]:
    """
    Automatically finds a baseline (normal) trace and an abnormal trace for comparison.
    
    This tool searches for:
    1. A fast/normal trace (baseline) - low latency, no errors
    2. A slow or error trace (abnormal) - high latency or contains errors
    
    Args:
        project_id: The GCP project ID. If not provided, uses GOOGLE_CLOUD_PROJECT env var.
        service_filter: Optional service name to filter traces (e.g., 'my-service').
        time_window_hours: How far back to search for traces (default 24 hours).
    
    Returns:
        A dictionary containing:
        - baseline_trace: A normal/fast trace for comparison
        - abnormal_trace: A slow or error trace for comparison
        - comparison_reason: Why these traces were selected
    """
    try:
        if not project_id:
            project_id = _get_project_id()
        
        client = _get_trace_client()
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=time_window_hours)
        
        base_filter = f"span:{service_filter}" if service_filter else ""
        
        # Find a slow trace (high latency)
        slow_traces = list_traces(
            project_id=project_id,
            filter_str=base_filter,
            start_time=start_time.isoformat(),
            end_time=now.isoformat(),
            limit=5,
            order_by="duration desc",  # Slowest first
        )
        
        # Find a fast trace (low latency)
        fast_traces = list_traces(
            project_id=project_id,
            filter_str=base_filter,
            start_time=start_time.isoformat(),
            end_time=now.isoformat(),
            limit=5,
            order_by="duration asc",  # Fastest first
        )
        
        abnormal_trace = None
        baseline_trace = None
        comparison_reason = ""
        
        # Get the slowest trace as abnormal
        if slow_traces and "error" not in slow_traces[0]:
            abnormal_trace_id = slow_traces[0]["trace_id"]
            abnormal_trace = fetch_trace(project_id, abnormal_trace_id)
            comparison_reason = "Selected slowest trace as abnormal (high latency)"
        
        # Get the fastest trace as baseline
        if fast_traces and "error" not in fast_traces[0]:
            baseline_trace_id = fast_traces[0]["trace_id"]
            baseline_trace = fetch_trace(project_id, baseline_trace_id)
            if comparison_reason:
                comparison_reason += "; selected fastest trace as baseline"
            else:
                comparison_reason = "Selected fastest trace as baseline"
        
        if not abnormal_trace and not baseline_trace:
            return {
                "error": "Could not find suitable traces for comparison",
                "message": f"No traces found in project {project_id} within the last {time_window_hours} hours",
                "suggestion": "Try running your application to generate traces, or adjust the time_window_hours parameter",
            }
        
        return {
            "baseline_trace": baseline_trace,
            "abnormal_trace": abnormal_trace,
            "comparison_reason": comparison_reason,
            "project_id": project_id,
            "time_window_hours": time_window_hours,
        }
    except Exception as e:
        logger.error(f"Error finding example traces: {e}")
        return {"error": str(e)}


def get_trace_by_url(trace_url: str) -> dict[str, Any]:
    """
    Parses a Cloud Console trace URL and fetches the trace data.
    
    Args:
        trace_url: A Google Cloud Console trace URL, e.g.:
            https://console.cloud.google.com/traces/list?project=my-project&tid=abc123
    
    Returns:
        The complete trace data, same as fetch_trace().
    """
    try:
        from urllib.parse import urlparse, parse_qs
        
        parsed = urlparse(trace_url)
        query_params = parse_qs(parsed.query)
        
        project_id = query_params.get("project", [None])[0]
        trace_id = query_params.get("tid", [None])[0]
        
        if not project_id or not trace_id:
            return {
                "error": "Could not parse project ID and trace ID from URL",
                "url": trace_url,
            }
        
        return fetch_trace(project_id, trace_id)
    except Exception as e:
        logger.error(f"Error parsing trace URL: {e}")
        return {"error": str(e)}
