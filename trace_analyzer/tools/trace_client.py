"""Tools for interacting with the Google Cloud Trace API."""

import json
import logging
import os
import statistics
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import errorreporting_v1beta1, monitoring_v3, trace_v1
from google.cloud.logging_v2.services.logging_service_v2 import LoggingServiceV2Client

from ..decorators import adk_tool

from ..decorators import adk_tool

logger = logging.getLogger(__name__)


@adk_tool
def list_log_entries(project_id: str, filter_str: str, limit: int = 10) -> str:
    """
    Lists log entries from Google Cloud Logging.

    Args:
        project_id: The Google Cloud Project ID.
        filter_str: The filter string to use.
        limit: The maximum number of log entries to return.

    Returns:
        A JSON string representing the list of log entries.

    Example filter_str: 'resource.type="gce_instance" AND severity="ERROR"'
    """
    try:
        client = LoggingServiceV2Client()
        resource_names = [f"projects/{project_id}"]
        entries = client.list_log_entries(
            request={
                "resource_names": resource_names,
                "filter": filter_str,
                "page_size": limit,
            }
        )
        results = []
        for entry in entries:
            payload_str = str(entry.payload)
            if len(payload_str) > 500:
                payload_str = payload_str[:500] + "...(truncated)"

            results.append(
                {
                    "timestamp": entry.timestamp.isoformat(),
                    "severity": entry.severity.name,
                    "payload": payload_str,
                    "resource": {
                        "type": entry.resource.type,
                        "labels": dict(entry.resource.labels),
                    },
                }
            )
        return json.dumps(results)
    except Exception as e:
        error_msg = f"Failed to list log entries: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def list_time_series(
    project_id: str, filter_str: str, minutes_ago: int = 60
) -> str:
    """
    Lists time series data from Google Cloud Monitoring.

    Args:
        project_id: The Google Cloud Project ID.
        filter_str: The filter string to use.
        minutes_ago: The number of minutes in the past to query.

    Returns:
        A JSON string representing the list of time series.

    Example filter_str: 'metric.type="compute.googleapis.com/instance/cpu/utilization" AND resource.labels.instance_id="12345"'
    """
    try:
        client = monitoring_v3.MetricServiceClient()
        project_name = f"projects/{project_id}"
        now = time.time()
        seconds = int(now)
        nanos = int((now - seconds) * 10**9)
        interval = monitoring_v3.TimeInterval(
            {
                "end_time": {"seconds": seconds, "nanos": nanos},
                "start_time": {
                    "seconds": seconds - (minutes_ago * 60),
                    "nanos": nanos,
                },
            }
        )
        results = client.list_time_series(
            name=project_name,
            filter=filter_str,
            interval=interval,
            view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
        )
        time_series_data = []
        for result in results:
            time_series_data.append(
                {
                    "metric": {
                        "type": result.metric.type,
                        "labels": dict(result.metric.labels),
                    },
                    "resource": {
                        "type": result.resource.type,
                        "labels": dict(result.resource.labels),
                    },
                    "points": [
                        {
                            "timestamp": point.interval.end_time.isoformat(),
                            "value": point.value.double_value,
                        }
                        for point in result.points
                    ],
                }
            )
        return json.dumps(time_series_data)
    except Exception as e:
        error_msg = f"Failed to list time series: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def list_error_events(project_id: str, minutes_ago: int = 60) -> str:
    """
    Lists error events from Google Cloud Error Reporting.

    Args:
        project_id: The Google Cloud Project ID.
        minutes_ago: The number of minutes in the past to query.

    Returns:
        A JSON string representing the list of error events.
    """
    try:
        client = errorreporting_v1beta1.ErrorStatsServiceClient()
        project_name = f"projects/{project_id}"
        time_range = errorreporting_v1beta1.QueryTimeRange()
        time_range.period = errorreporting_v1beta1.QueryTimeRange.Period.PERIOD_1_HOUR
        request = errorreporting_v1beta1.ListEventsRequest(
            project_name=project_name,
            group_id=None,
            time_range=time_range,
            page_size=100,
        )

        events = client.list_events(request=request)

        results = []
        for event in events:
            results.append(
                {
                    "event_time": event.event_time.isoformat(),
                    "message": event.message,
                    "service_context": {
                        "service": event.service_context.service,
                        "version": event.service_context.version,
                    },
                }
            )
        return json.dumps(results)
    except Exception as e:
        error_msg = f"Failed to list error events: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

@adk_tool
def get_logs_for_trace(project_id: str, trace_id: str, limit: int = 100) -> str:
    """
    Fetches log entries correlated with a specific trace ID.

    Args:
        project_id: The Google Cloud Project ID.
        trace_id: The unique trace ID.
        limit: Max logs to return.

    Returns:
        JSON list of log entries.
    """
    filter_str = f'trace="projects/{project_id}/traces/{trace_id}"'
    return list_log_entries(project_id, filter_str, limit)





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


def fetch_trace_data(trace_id_or_json: str | dict[str, Any], project_id: str | None = None) -> dict[str, Any]:
    """
    Helper to fetch trace data by ID or from JSON/dict.
    Commonly used across analysis tools to handle flexible inputs.
    """
    # Check if it's already a dictionary
    if isinstance(trace_id_or_json, dict):
        if "trace_id" in trace_id_or_json or "spans" in trace_id_or_json or "error" in trace_id_or_json:
            return trace_id_or_json
        return {"error": "Invalid trace dictionary provided."}

    # Check if it's a JSON string containing a trace
    if isinstance(trace_id_or_json, str) and trace_id_or_json.strip().startswith("{"):
        try:
            data = json.loads(trace_id_or_json)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            return {"error": "Failed to parse trace JSON"}

    if not project_id:
        try:
            project_id = _get_project_id()
        except ValueError:
             pass

    if not project_id:
         return {"error": "Project ID required to fetch trace."}

    trace_json = fetch_trace(project_id, trace_id_or_json)
    try:
        if isinstance(trace_json, dict):
            return trace_json
        data = json.loads(trace_json)
        if data and "error" in data:
            return data
        return data
    except json.JSONDecodeError:
        return {"error": "Invalid trace JSON"}



@adk_tool
def fetch_trace(project_id: str, trace_id: str) -> str:
    """
    Fetches a specific trace by ID.

    Uses caching to avoid redundant API calls when the same trace
    is requested multiple times (e.g., by different sub-agents).

    Args:
        project_id: The Google Cloud Project ID.
        trace_id: The unique hex ID of the trace.

    Returns:
        A dictionary representation of the trace, including all spans.
    """
    # Check cache first
    from .trace_cache import get_trace_cache
    cache = get_trace_cache()

    cached = cache.get(trace_id)
    if cached:
        logger.debug(f"Cache hit for trace {trace_id}, skipping API call")
        return cached

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

        # Cache the result before returning
        result_json = json.dumps(result)
        cache.put(trace_id, result_json)

        return result_json

    except Exception as e:
        error_msg = f"Failed to fetch trace: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def list_traces(
    project_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 10,
    filter_str: str = "",
    min_latency_ms: int | None = None,
    error_only: bool = False,
    attributes: dict[str, str] | None = None
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

    Example filter_str: 'latency:500ms error:true' or '/http/status_code:500'
    """
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
        error_msg = f"Failed to list traces: {e!s}"
        logger.error(error_msg)
        return json.dumps([{"error": error_msg}])


def _calculate_anomaly_score(
    trace: dict[str, Any],
    mean_latency: float,
    stdev_latency: float,
    has_error: bool = False
) -> float:
    """
    Calculate a composite anomaly score for a trace.

    The score combines multiple signals:
    - Latency z-score (how many std devs from mean)
    - Error presence (significant boost)
    - Extreme latency bonus (for very slow traces)

    Args:
        trace: Trace data dict with duration_ms.
        mean_latency: Mean latency across sample.
        stdev_latency: Standard deviation of latencies.
        has_error: Whether this trace has errors.

    Returns:
        Composite anomaly score (higher = more anomalous).
    """
    score = 0.0
    duration = trace.get("duration_ms", 0)

    # Z-score component (0-5 points typical)
    if stdev_latency > 0:
        z_score = (duration - mean_latency) / stdev_latency
        score += max(0, z_score)  # Only positive z-scores count
    elif duration > mean_latency:
        # If no variance, any deviation is significant
        score += 3.0

    # Error component (big boost)
    if has_error:
        score += 5.0

    # Extreme latency bonus (>3x mean)
    if mean_latency > 0 and duration > mean_latency * 3:
        score += 2.0

    return score


def validate_trace(trace_data: str | dict) -> dict[str, Any]:
    """
    Validates trace data for completeness and quality.

    Checks:
    - Has required fields (trace_id, spans)
    - Has valid span structure
    - Has reasonable duration
    - Spans have timestamps

    Args:
        trace_data: Trace data as JSON string or dict.

    Returns:
        Validation result with 'valid' boolean and 'issues' list.
    """
    issues = []

    if isinstance(trace_data, str):
        try:
            data = json.loads(trace_data)
        except json.JSONDecodeError as e:
            return {"valid": False, "issues": [f"Invalid JSON: {e!s}"]}
    else:
        data = trace_data

    # Check for error response
    if "error" in data:
        return {"valid": False, "issues": [data["error"]]}

    # Required fields
    if not data.get("trace_id"):
        issues.append("Missing trace_id")

    spans = data.get("spans", [])
    if not spans:
        issues.append("No spans in trace")
    else:
        # Validate span structure
        for i, span in enumerate(spans):
            if not span.get("span_id"):
                issues.append(f"Span {i} missing span_id")
            if not span.get("name"):
                issues.append(f"Span {i} missing name")
            if not span.get("start_time"):
                issues.append(f"Span {i} missing start_time")
            if not span.get("end_time"):
                issues.append(f"Span {i} missing end_time")

        # Check for reasonable structure
        if len(spans) > 1000:
            issues.append(f"Unusually large trace with {len(spans)} spans")

    # Check duration
    duration = data.get("duration_ms", 0)
    if duration <= 0:
        issues.append("Invalid or missing duration")
    elif duration > 300000:  # 5 minutes
        issues.append(f"Unusually long duration: {duration}ms")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "span_count": len(spans),
        "duration_ms": duration
    }


@adk_tool
def find_example_traces(
    project_id: str | None = None,
    prefer_errors: bool = True,
    min_sample_size: int = 20
) -> str:
    """
    Intelligently discovers representative baseline and anomaly traces using
    a hybrid selection algorithm.

    The algorithm:
    1. Fetches recent traces to build a statistical model
    2. Also fetches recent error traces for multi-signal analysis
    3. Scores traces using composite anomaly scoring
    4. Validates selected traces before returning

    Args:
        prefer_errors: If True, error traces get higher anomaly scores.
        min_sample_size: Minimum traces needed for statistical analysis.

    Returns:
        JSON string with 'baseline', 'anomaly', 'stats', and 'validation' keys.
    """
    try:
        try:
            if not project_id:
                project_id = _get_project_id()
        except ValueError:
            return json.dumps({"error": "GOOGLE_CLOUD_PROJECT not set"})

        # 1. Fetch recent traces for statistical baseline
        raw_traces = list_traces(project_id, limit=50)
        traces = json.loads(raw_traces)

        if isinstance(traces, list) and len(traces) > 0 and "error" in traces[0]:
            return raw_traces

        if not traces:
            return json.dumps({"error": "No traces found in the last hour."})

        # 2. Fetch error traces separately for hybrid selection
        error_trace_ids = set()
        if prefer_errors:
            error_traces_json = list_traces(project_id, limit=10, error_only=True)
            error_traces = json.loads(error_traces_json)
            if error_traces and not (isinstance(error_traces, list) and "error" in error_traces[0]):
                error_trace_ids = {t.get("trace_id") for t in error_traces if t.get("trace_id")}
                # Merge error traces into main list if not already present
                existing_ids = {t.get("trace_id") for t in traces}
                for et in error_traces:
                    if et.get("trace_id") not in existing_ids:
                        et["has_error"] = True
                        traces.append(et)

        # 3. Extract valid traces with latencies
        valid_traces = [t for t in traces if t.get("duration_ms", 0) > 0]
        if len(valid_traces) < 2:
            return json.dumps({"error": "Insufficient traces with valid duration found."})

        latencies = [t["duration_ms"] for t in valid_traces]
        latencies.sort()

        # 4. Calculate statistical metrics
        p50 = statistics.median(latencies)
        p95 = latencies[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0]
        p99 = latencies[int(len(latencies) * 0.99)] if len(latencies) > 1 else latencies[0]
        mean = statistics.mean(latencies)
        stdev = statistics.stdev(latencies) if len(latencies) > 1 else 0

        # 5. Score all traces for anomaly detection
        for trace in valid_traces:
            has_error = (
                trace.get("has_error", False) or
                trace.get("trace_id") in error_trace_ids
            )
            trace["_anomaly_score"] = _calculate_anomaly_score(
                trace, mean, stdev, has_error
            )
            trace["_has_error"] = has_error

        # 6. Select baseline (closest to P50, prefer no errors)
        baseline_candidates = [
            t for t in valid_traces
            if not t.get("_has_error", False)
        ]
        if not baseline_candidates:
            baseline_candidates = valid_traces

        baseline = min(
            baseline_candidates,
            key=lambda x: abs(x["duration_ms"] - p50)
        )

        # 7. Select anomaly (highest anomaly score, excluding baseline)
        anomaly_candidates = [
            t for t in valid_traces
            if t.get("trace_id") != baseline.get("trace_id")
        ]
        if anomaly_candidates:
            anomaly = max(anomaly_candidates, key=lambda x: x.get("_anomaly_score", 0))
        else:
            # Fallback: just pick the slowest trace
            anomaly = max(valid_traces, key=lambda x: x.get("duration_ms", 0))

        # 8. Add selection reasoning
        baseline["_selection_reason"] = f"Closest to P50 ({p50:.1f}ms)"
        anomaly_score = anomaly.get("_anomaly_score", 0)
        if anomaly.get("_has_error"):
            anomaly["_selection_reason"] = f"Error trace with anomaly score {anomaly_score:.2f}"
        else:
            anomaly["_selection_reason"] = f"High latency anomaly score {anomaly_score:.2f}"

        # 9. Clean up internal fields before returning
        for trace in [baseline, anomaly]:
            trace.pop("_anomaly_score", None)
            trace.pop("_has_error", None)

        # 10. Validate both traces exist (light validation - full validation requires fetch)
        validation = {
            "baseline_valid": baseline.get("trace_id") is not None,
            "anomaly_valid": anomaly.get("trace_id") is not None,
            "sample_adequate": len(valid_traces) >= min_sample_size,
            "latency_variance_detected": stdev > 0
        }

        return json.dumps({
            "stats": {
                "count": len(valid_traces),
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
                "p99_ms": round(p99, 2),
                "mean_ms": round(mean, 2),
                "stdev_ms": round(stdev, 2) if stdev else 0,
                "error_traces_found": len(error_trace_ids)
            },
            "baseline": baseline,
            "anomaly": anomaly,
            "validation": validation,
            "selection_method": "hybrid_multi_signal"
        })

    except Exception as e:
        error_msg = f"Failed to find example traces: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def get_trace_by_url(url: str) -> str:
    """
    Parses a Cloud Console URL to extract trace ID and fetch the trace.

    Args:
        url: The full URL from Google Cloud Console trace view.

    Returns:
        The fetched trace data.
    """
    try:
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        project_id = params.get("project", [None])[0]

        trace_id = None
        if "tid" in params:
                trace_id = params["tid"][0]
        elif "details" in parsed.path:
            parts = parsed.path.split("/")
            # Handle both /details/abc123 and /trace-details/abc123
            for i, part in enumerate(parts):
                if "details" in part and i + 1 < len(parts):
                    trace_id = parts[i+1]
                    break
        
        # Fallback: if we still don't have trace_id, look for last segment that looks like a hex ID
        if not trace_id:
             for part in reversed(parsed.path.split("/")):
                  if part and all(c in "0123456789abcdefABCDEF" for c in part) and len(part) >= 32:
                       trace_id = part
                       break

        if not project_id or not trace_id:
            return json.dumps({"error": "Could not parse project_id or trace_id from URL"})

        return fetch_trace(project_id, trace_id)

    except Exception as e:
        error_msg = f"Failed to get trace by URL: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
