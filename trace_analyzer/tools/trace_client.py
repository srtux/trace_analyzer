"""Tools for interacting with the Google Cloud Trace API."""

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union, Tuple
import json
import time
import logging
import statistics

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


class TraceFilterBuilder:
    """Helper to construct Cloud Trace filter strings."""

    def __init__(self):
        self.terms = []

    def add_latency(self, duration_ms: int):
        self.terms.append(f"latency:{duration_ms}ms")
        return self

    def add_root_span_name(self, name: str, exact: bool = False):
        # root:[NAME_PREFIX] or +root:[NAME]
        term = f"root:{name}"
        if exact:
            term = f"+{term}"
        self.terms.append(term)
        return self

    def add_span_name(self, name: str, exact: bool = False, root_span: bool = False):
        # span:[NAME_PREFIX] or +span:[NAME]
        # with root_span=True: ^span:... or +^span:...
        prefix = "^" if root_span else ""
        op = "+" if exact else ""
        term = f"{op}{prefix}span:{name}"
        self.terms.append(term)
        return self

    def add_attribute(self, key: str, value: Any, exact: bool = False, root_span: bool = False):
        """
        Adds an attribute filter.
        Args:
            key: The attribute key (e.g. 'label', '/http/status_code', 'service.name').
            value: The attribute value.
            exact: If True, uses exact match (+) for the value.
            root_span: If True, restricts to root span (^).
        """
        str_val = str(value)
        # Quote value if it contains special characters
        if not re.match(r'^[a-zA-Z0-9./_-]+$', str_val):
            # Escape double quotes and backslashes
            escaped_val = str_val.replace('\\', '\\\\').replace('"', '\\"')
            str_val = f'"{escaped_val}"'

        prefix = "^" if root_span else ""
        op = "+" if exact else ""

        # Cloud Trace syntax: [^][+]key:value
        term = f"{op}{prefix}{key}:{str_val}"
        self.terms.append(term)
        return self

    def build(self) -> str:
        return " ".join(self.terms)


def get_current_time() -> str:
    """
    Returns the current UTC time in ISO format. 
    Use this to calculate relative time ranges (e.g., 'now - 1 hour') for list_traces.
    """
    return datetime.now(timezone.utc).isoformat()


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
            
            trace_obj = client.get_trace(project_id=project_id, trace_id=trace_id)
            
            spans = []
            trace_start = None
            trace_end = None

            for span_proto in trace_obj.spans:
                # span_proto.start_time is a standard python datetime in newer google-cloud libraries (proto-plus)
                s_start = span_proto.start_time.timestamp()
                s_end = span_proto.end_time.timestamp()

                if trace_start is None or s_start < trace_start:
                    trace_start = s_start
                if trace_end is None or s_end > trace_end:
                    trace_end = s_end

                spans.append({
                    "span_id": span_proto.span_id,
                    "name": span_proto.name,
                    "start_time": span_proto.start_time.isoformat(),
                    "end_time": span_proto.end_time.isoformat(),
                    "parent_span_id": span_proto.parent_span_id,
                    "labels": dict(span_proto.labels),
                })
            
            duration_ms = (trace_end - trace_start) * 1000 if trace_start and trace_end else 0

            result = {
                "trace_id": trace_obj.trace_id,
                "project_id": trace_obj.project_id,
                "spans": spans,
                "span_count": len(spans),
                "duration_ms": duration_ms
            }
            span.set_attribute("trace_analyzer.span_count", len(spans))
            return json.dumps(result)
            
        except Exception as e:
            span.record_exception(e)
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
    limit: int = 10,
    filter_str: str = "",
    min_latency_ms: Optional[int] = None,
    error_only: bool = False,
    attributes: Optional[Dict[str, str]] = None
) -> str:
    """
    Lists recent traces with advanced filtering capabilities.
    
    Args:
        project_id: The GCP project ID.
        start_time: ISO timestamp for start of window.
        end_time: ISO timestamp for end of window.
        limit: Max number of traces to return.
        filter_str: Raw filter string (overrides other filters if provided).
        min_latency_ms: Minimum latency in milliseconds.
        error_only: If True, filters for traces with errors (label:error:true or /http/status_code:500).
        attributes: Dictionary of attribute key-values to filter by (exact match).
    
    Returns:
        List of trace summaries.
    """
    ts_start = time.time()
    success = True

    with tracer.start_as_current_span("list_traces") as span:
        span.set_attribute("trace_analyzer.project_id", project_id)

        # Build filter string if not provided
        final_filter = filter_str
        if not final_filter:
            filters = []
            if min_latency_ms:
                filters.append(f"latency:{min_latency_ms}ms")

            if error_only:
                # Common ways to find errors in Cloud Trace.
                # "error:true" matches the standard error label.
                filters.append("error:true")

            if attributes:
                for k, v in attributes.items():
                    # Standard Cloud Trace filter is key:value
                    filters.append(f"{k}:{v}")

            final_filter = " ".join(filters)

        span.set_attribute("trace_analyzer.filter", final_filter)
        
        try:
            client = trace_v1.TraceServiceClient()
            
            now = datetime.now(timezone.utc)
            if not end_time:
                end_dt = now
            else:
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                
            if not start_time:
                start_dt = now - timedelta(hours=1)
            else:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            
            # Note: proto-plus handles datetime conversion automatically for Timestamp fields
            
            request = trace_v1.ListTracesRequest(
                project_id=project_id,
                start_time=start_dt, # Pass datetime directly
                end_time=end_dt,     # Pass datetime directly
                page_size=limit,
                filter=final_filter,
                # Use ROOTSPAN view to get at least the root span for duration calculation.
                # MINIMAL view only returns trace_id and project_id.
                view=trace_v1.ListTracesRequest.ViewType.ROOTSPAN
            )
            
            traces = []
            page_result = client.list_traces(request=request)
            
            for trace in page_result:
                # Calculate duration
                duration_ms = 0
                start_ts = None

                # In ROOTSPAN view, we should have at least the root span.
                if trace.spans:
                    # Just use the root span's duration as a proxy if we don't have all spans.
                    # Usually root span covers the whole request.
                    # Or check all available spans.
                    starts = []
                    ends = []
                    for s in trace.spans:
                         # s.start_time is datetime
                         starts.append(s.start_time.timestamp())
                         ends.append(s.end_time.timestamp())

                    if starts and ends:
                        start_ts = min(starts)
                        duration_ms = (max(ends) - start_ts) * 1000

                traces.append({
                    "trace_id": trace.trace_id,
                    "timestamp": datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat() if start_ts else None,
                    "duration_ms": duration_ms,
                    "project_id": trace.project_id
                })
                
                if len(traces) >= limit:
                    break
            
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
    Intelligently discovers representative baseline and anomaly traces.
    
    Returns:
        JSON string with 'baseline' and 'anomaly' keys containing trace summaries.
    """
    ts_start = time.time()
    success = True
    
    with tracer.start_as_current_span("find_example_traces") as span:
        try:
            try:
                project_id = _get_project_id()
            except ValueError:
                return json.dumps({"error": "GOOGLE_CLOUD_PROJECT not set"})
            
            # Default Strategy:
            # 1. Look for a slow root span first (e.g. latency > 1s, or just fetch recent and find P95)
            # The user requested: "By default it should look for root spans that take a long time."
            # We can try to fetch traces with latency > 1000ms.

            anomaly = None
            baseline = None

            # Try to find a slow trace directly first
            # We'll fetch 10 recent traces that took longer than 1s.
            filter_builder = TraceFilterBuilder()
            filter_builder.add_latency(1000)

            slow_traces_json = list_traces(project_id, limit=10, filter_str=filter_builder.build())
            slow_traces = json.loads(slow_traces_json)

            if isinstance(slow_traces, list) and len(slow_traces) > 0 and "error" not in slow_traces[0]:
                 # We found slow traces. Pick the slowest.
                 slow_traces.sort(key=lambda x: x.get("duration_ms", 0))
                 anomaly = slow_traces[-1]
                 span.set_attribute("trace_stats.strategy", "latency_filter")
            else:
                 # Fallback: fetch general recent traces and do stats
                 raw_traces = list_traces(project_id, limit=50)
                 traces = json.loads(raw_traces)

                 if isinstance(traces, list) and len(traces) > 0 and "error" not in traces[0]:
                     valid_traces = [t for t in traces if t.get("duration_ms", 0) > 0]
                     if valid_traces:
                        latencies = [t["duration_ms"] for t in valid_traces]
                        latencies.sort()
                        p95 = latencies[int(len(latencies) * 0.95)]
                        candidates = [t for t in valid_traces if t["duration_ms"] >= p95]
                        anomaly = candidates[-1] if candidates else valid_traces[-1]
                        span.set_attribute("trace_stats.strategy", "statistical_p95")

            if not anomaly:
                return json.dumps({"error": "No valid traces found to analyze."})

            # Now find a similar trace that took shorter.
            # We need the root span name of the anomaly.
            # But list_traces output (summary) doesn't have the name.
            # We need to fetch the full trace details for the anomaly to get the root name.
            anomaly_full_json = fetch_trace(project_id, anomaly["trace_id"])
            anomaly_full = json.loads(anomaly_full_json)

            if "error" in anomaly_full:
                 return json.dumps({"error": f"Failed to fetch details for anomaly trace: {anomaly_full['error']}"})

            # Find root span name
            # Assuming the first span or one without parent is root.
            # fetch_trace returns spans.
            root_span_name = None
            for s in anomaly_full.get("spans", []):
                if not s.get("parent_span_id"):
                    root_span_name = s.get("name")
                    break

            if not root_span_name:
                # Fallback: use the first span's name
                if anomaly_full.get("spans"):
                    root_span_name = anomaly_full["spans"][0].get("name")

            if root_span_name:
                # Search for shorter traces with same root name
                fb = TraceFilterBuilder()
                fb.add_root_span_name(root_span_name, exact=True)
                # We can't filter by "latency < X" in Cloud Trace API (only >=).
                # So we fetch recent ones with same name and filter in memory.

                candidates_json = list_traces(project_id, limit=20, filter_str=fb.build())
                candidates = json.loads(candidates_json)

                if isinstance(candidates, list) and "error" not in candidates[0]:
                    # Filter for shorter duration
                    shorter = [t for t in candidates if t.get("duration_ms", 0) < anomaly["duration_ms"]]
                    if shorter:
                        # Pick the fastest one? or median?
                        # User said "took shorter". Let's pick the fastest one as a good baseline contrast.
                        shorter.sort(key=lambda x: x.get("duration_ms", 0))
                        baseline = shorter[0]

            if not baseline:
                # If we couldn't find a baseline by name, fall back to statistical baseline from the initial batch if we had one
                # Or just fetch recent traces again.
                raw_traces = list_traces(project_id, limit=50)
                traces = json.loads(raw_traces)
                if isinstance(traces, list) and len(traces) > 0 and "error" not in traces[0]:
                     valid_traces = [t for t in traces if t.get("duration_ms", 0) > 0]
                     if valid_traces:
                        # Pick median
                         latencies = [t["duration_ms"] for t in valid_traces]
                         latencies.sort()
                         p50 = statistics.median(latencies)
                         baseline = min(valid_traces, key=lambda x: abs(x["duration_ms"] - p50))

            return json.dumps({
                "anomaly": anomaly,
                "baseline": baseline,
                "note": "Anomaly found via latency filter (>1s) or P95. Baseline found via same root span name or P50."
            })

        except Exception as e:
            span.record_exception(e)
            success = False
            error_msg = f"Failed to find example traces: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})
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
