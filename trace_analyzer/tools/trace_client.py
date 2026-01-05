"""Tools for interacting with the Google Cloud Trace API."""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union
import json
import time
import logging

from google.cloud import trace_v1
from google.protobuf.timestamp_pb2 import Timestamp

from ..telemetry import get_tracer, get_meter

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

def _record_telemetry(func_name: str, success: bool = True, duration_ms: float = 0.0):
    attributes = {
        "code.function": func_name,
        "code.namespace": __name__,
        "success": str(success).lower(),
        "trace_analyzer.tool.name": func_name,
    }
    logger.debug(f"Recording telemetry for {func_name}: success={success}, duration={duration_ms}ms, attributes={attributes}")
    execution_count.add(1, attributes)
    execution_duration.record(duration_ms, attributes)


def _get_project_id() -> str:
    """Get the GCP project ID from environment."""
    project_id = os.environ.get("TRACE_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT or TRACE_PROJECT_ID environment variable must be set")
    return project_id


def fetch_trace(project_id: str, trace_id: str) -> str:
    """
    Fetches a specific trace by ID.
    
    Args:
        project_id: The Google Cloud Project ID.
        trace_id: The unique hex ID of the trace.
    
    Returns:
        A dictionary representation of the trace, including all spans.
    """
    start_time = time.time()
    success = True
    
    with tracer.start_as_current_span("fetch_trace") as span:
        span.set_attribute("trace_analyzer.project_id", project_id)
        span.set_attribute("trace_analyzer.trace_id", trace_id)
        span.set_attribute("code.function", "fetch_trace")
        
        try:
            client = trace_v1.TraceServiceClient()
            
            # v1 TraceServiceClient.get_trace takes project_id and trace_id
            trace_obj = client.get_trace(project_id=project_id, trace_id=trace_id)
            
            spans = []
            for span_proto in trace_obj.spans:
                spans.append({
                    "span_id": span_proto.span_id,
                    "name": span_proto.name,
                    "start_time": span_proto.start_time.isoformat(),
                    "end_time": span_proto.end_time.isoformat(),
                    "parent_span_id": span_proto.parent_span_id,
                    "labels": dict(span_proto.labels),
                })
            
            result = {
                "trace_id": trace_obj.trace_id,
                "project_id": trace_obj.project_id,
                "spans": spans,
                "span_count": len(spans),
            }
            span.set_attribute("trace_analyzer.span_count", len(spans))
            return json.dumps(result)
            
        except Exception as e:
            span.record_exception(e)
            from opentelemetry.trace import Status, StatusCode
            span.set_status(Status(StatusCode.ERROR, str(e))) 
            success = False
            error_msg = f"Failed to fetch trace: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})
        finally:
            duration_ms = (time.time() - start_time) * 1000
            _record_telemetry("fetch_trace", success, duration_ms)


def list_traces(
    project_id: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 5,
    filter_str: str = ""
) -> str:
    """
    Lists recent traces for a project.
    
    Args:
        project_id: The GCP project ID.
        start_time: ISO timestamp for start of window (default: 1 hour ago).
        end_time: ISO timestamp for end of window (default: now).
        limit: Max number of traces to return.
        filter_str: Optional filter string.
    
    Returns:
        List of trace summaries.
    """
    ts_start = time.time()
    success = True

    with tracer.start_as_current_span("list_traces") as span:
        span.set_attribute("trace_analyzer.project_id", project_id)
        span.set_attribute("trace_analyzer.limit", limit)
        span.set_attribute("code.function", "list_traces")
        if filter_str:
            span.set_attribute("trace_analyzer.filter", filter_str)
        
        try:
            client = trace_v1.TraceServiceClient()
            
            # Default time range: last 1 hour
            now = datetime.now(timezone.utc)
            if not end_time:
                end_dt = now
            else:
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                
            if not start_time:
                start_dt = now - timedelta(hours=1)
            else:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

            span.set_attribute("trace_analyzer.time_range_start", start_dt.isoformat())
            span.set_attribute("trace_analyzer.time_range_end", end_dt.isoformat())
            
            start_timestamp = Timestamp()
            start_timestamp.FromDatetime(start_dt)
            
            end_timestamp = Timestamp()
            end_timestamp.FromDatetime(end_dt)
            
            request = trace_v1.ListTracesRequest(
                project_id=project_id,
                start_time=start_timestamp,
                end_time=end_timestamp,
                page_size=limit,
                filter=filter_str
            )
            
            traces = []
            page_result = client.list_traces(request=request)
            
            for trace in page_result:
                duration_ms = 0
                # Roughly estimate duration from spans if available, or just header
                if trace.spans:
                    starts = [s.start_time for s in trace.spans]
                    ends = [s.end_time for s in trace.spans]
                    if starts and ends:
                        duration_ms = (max(ends) - min(starts)).total_seconds() * 1000

                traces.append({
                    "trace_id": trace.trace_id,
                    "timestamp": trace.spans[0].start_time.isoformat() if trace.spans else None,
                    "duration_ms": duration_ms,
                    "project_id": trace.project_id
                })
                
                if len(traces) >= limit:
                    break
            
            span.set_attribute("trace_analyzer.trace_count", len(traces))
            return json.dumps(traces)

        except Exception as e:
            span.record_exception(e)
            success = False
            error_msg = f"Failed to list traces: {str(e)}"
            logger.error(error_msg)
            return json.dumps([{"error": error_msg}])
        finally:
            duration_ms = (time.time() - ts_start) * 1000
            _record_telemetry("list_traces", success, duration_ms)


def find_example_traces() -> str:
    """
    Finds example traces from the current environment/project.
    
    Returns:
        A list of trace summaries found in the environment.
    """
    ts_start = time.time()
    success = True
    
    with tracer.start_as_current_span("find_example_traces") as span:
        span.set_attribute("code.function", "find_example_traces")
        try:
            try:
                project_id = _get_project_id()
            except ValueError:
                return json.dumps([{"error": "GOOGLE_CLOUD_PROJECT or TRACE_PROJECT_ID not set"}])
            
            # Use list_traces to find some examples
            return list_traces(project_id, limit=3)
        except Exception as e:
            span.record_exception(e)
            success = False
            error_msg = f"Failed to find example traces: {str(e)}"
            logger.error(error_msg)
            return json.dumps([{"error": error_msg}])
        finally:
            duration_ms = (time.time() - ts_start) * 1000
            _record_telemetry("find_example_traces", success, duration_ms)


def get_trace_by_url(url: str) -> str:
    """
    Parses a Cloud Console URL to extract trace ID and fetch the trace.
    
    Args:
        url: The full URL from Google Cloud Console trace view.
    
    Returns:
        The fetched trace data.
    """
    ts_start = time.time()
    success = True
    
    with tracer.start_as_current_span("get_trace_by_url") as span:
        span.set_attribute("trace_analyzer.url", url)
        span.set_attribute("code.function", "get_trace_by_url")
        
        try:
            from urllib.parse import urlparse, parse_qs
            
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            project_id = params.get("project", [None])[0]
            
            trace_id = None
            if "tid" in params:
                 trace_id = params["tid"][0]
            elif "details" in parsed.path:
                parts = parsed.path.split("/")
                if "details" in parts:
                    idx = parts.index("details")
                    if idx + 1 < len(parts):
                        trace_id = parts[idx+1]
            
            if not project_id or not trace_id:
                return json.dumps({"error": "Could not parse project_id or trace_id from URL"})
                
            return fetch_trace(project_id, trace_id)

        except Exception as e:
            span.record_exception(e)
            success = False
            error_msg = f"Failed to parse URL/fetch trace: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})
        finally:
            duration_ms = (time.time() - ts_start) * 1000
            _record_telemetry("get_trace_by_url", success, duration_ms)
