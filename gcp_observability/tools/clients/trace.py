"""Cloud Trace API clients for fetching and listing traces."""

import json
import logging
import os
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import trace_v1

from ..common import adk_tool
from ..common.cache import get_data_cache

logger = logging.getLogger(__name__)


def _get_project_id() -> str:
    """Get the GCP project ID from environment."""
    project_id = os.environ.get("TRACE_PROJECT_ID") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT"
    )
    if not project_id:
        raise ValueError(
            "GOOGLE_CLOUD_PROJECT or TRACE_PROJECT_ID environment variable must be set"
        )
    return project_id


def get_current_time() -> str:
    """
    Returns the current UTC time in ISO format.
    Use this to calculate relative time ranges for list_traces.
    """
    return datetime.now(timezone.utc).isoformat()


def fetch_trace_data(  # noqa: C901
    trace_id_or_json: str | dict[str, Any], project_id: str | None = None
) -> dict[str, Any]:
    """
    Helper to fetch trace data by ID or from JSON/dict.
    Commonly used across analysis tools to handle flexible inputs.
    """
    # Check if it's already a dictionary
    if isinstance(trace_id_or_json, dict):
        if (
            "trace_id" in trace_id_or_json
            or "spans" in trace_id_or_json
            or "error" in trace_id_or_json
        ):
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
    Fetches a specific trace by ID from Cloud Trace API.

    Uses caching to avoid redundant API calls when the same trace
    is requested multiple times (e.g., by different sub-agents).

    Args:
        project_id: The Google Cloud Project ID.
        trace_id: The unique hex ID of the trace.

    Returns:
        A JSON string representation of the trace, including all spans.
    """
    # Check cache first
    cache = get_data_cache()

    cached = cache.get(f"trace:{trace_id}")
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
            s_start = span_proto.start_time.timestamp()
            s_end = span_proto.end_time.timestamp()

            if trace_start is None or s_start < trace_start:
                trace_start = s_start
            if trace_end is None or s_end > trace_end:
                trace_end = s_end

            spans.append(
                {
                    "span_id": span_proto.span_id,
                    "name": span_proto.name,
                    "start_time": span_proto.start_time.isoformat(),
                    "end_time": span_proto.end_time.isoformat(),
                    "parent_span_id": span_proto.parent_span_id,
                    "labels": dict(span_proto.labels),
                }
            )

        duration_ms = (
            (trace_end - trace_start) * 1000 if trace_start and trace_end else 0
        )

        result = {
            "trace_id": trace_obj.trace_id,
            "project_id": trace_obj.project_id,
            "spans": spans,
            "span_count": len(spans),
            "duration_ms": duration_ms,
        }

        # Cache the result before returning
        result_json = json.dumps(result)
        cache.put(f"trace:{trace_id}", result_json)

        return result_json

    except Exception as e:
        error_msg = f"Failed to fetch trace: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def list_traces(  # noqa: C901
    project_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 10,
    filter_str: str = "",
    min_latency_ms: int | None = None,
    error_only: bool = False,
    attributes: dict[str, str] | None = None,
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
        error_only: If True, filters for traces with errors.
        attributes: Dictionary of attribute key-values to filter by.

    Returns:
        JSON list of trace summaries.

    Example filter_str: 'latency:500ms error:true' or '/http/status_code:500'
    """
    # Build filter string if not provided
    final_filter = filter_str
    if not final_filter:
        filters = []
        if min_latency_ms:
            filters.append(f"latency:{min_latency_ms}ms")

        if error_only:
            filters.append("error:true")

        if attributes:
            for k, v in attributes.items():
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

        request = trace_v1.ListTracesRequest(
            project_id=project_id,
            start_time=start_dt,
            end_time=end_dt,
            page_size=limit,
            filter=final_filter,
            view=trace_v1.ListTracesRequest.ViewType.ROOTSPAN,
        )

        traces = []
        page_result = client.list_traces(request=request)

        for trace in page_result:
            duration_ms = 0
            start_ts = None

            if trace.spans:
                starts = []
                ends = []
                for s in trace.spans:
                    starts.append(s.start_time.timestamp())
                    ends.append(s.end_time.timestamp())

                if starts and ends:
                    start_ts = min(starts)
                    duration_ms = (max(ends) - start_ts) * 1000

            traces.append(
                {
                    "trace_id": trace.trace_id,
                    "timestamp": datetime.fromtimestamp(
                        start_ts, tz=timezone.utc
                    ).isoformat()
                    if start_ts
                    else None,
                    "duration_ms": duration_ms,
                    "project_id": trace.project_id,
                }
            )

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
    has_error: bool = False,
) -> float:
    """
    Calculate a composite anomaly score for a trace.

    The score combines multiple signals:
    - Latency z-score (how many std devs from mean)
    - Error presence (significant boost)
    - Extreme latency bonus (for very slow traces)
    """
    score = 0.0
    duration = trace.get("duration_ms", 0)

    # Z-score component
    if stdev_latency > 0:
        z_score = (duration - mean_latency) / stdev_latency
        score += max(0, z_score)
    elif duration > mean_latency:
        score += 3.0

    # Error component
    if has_error:
        score += 5.0

    # Extreme latency bonus (>3x mean)
    if mean_latency > 0 and duration > mean_latency * 3:
        score += 2.0

    return score


def validate_trace(trace_data: str | dict) -> dict[str, Any]:  # noqa: C901
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

    if "error" in data:
        return {"valid": False, "issues": [data["error"]]}

    if not data.get("trace_id"):
        issues.append("Missing trace_id")

    spans = data.get("spans", [])
    if not spans:
        issues.append("No spans in trace")
    else:
        for i, span in enumerate(spans):
            if not span.get("span_id"):
                issues.append(f"Span {i} missing span_id")
            if not span.get("name"):
                issues.append(f"Span {i} missing name")
            if not span.get("start_time"):
                issues.append(f"Span {i} missing start_time")
            if not span.get("end_time"):
                issues.append(f"Span {i} missing end_time")

        if len(spans) > 1000:
            issues.append(f"Unusually large trace with {len(spans)} spans")

    duration = data.get("duration_ms", 0)
    if duration <= 0:
        issues.append("Invalid or missing duration")
    elif duration > 300000:
        issues.append(f"Unusually long duration: {duration}ms")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "span_count": len(spans),
        "duration_ms": duration,
    }


@adk_tool
def find_example_traces(  # noqa: C901
    project_id: str | None = None, prefer_errors: bool = True, min_sample_size: int = 20
) -> str:
    """
    Intelligently discovers representative baseline and anomaly traces.

    The algorithm:
    1. Fetches recent traces to build a statistical model
    2. Also fetches recent error traces for multi-signal analysis
    3. Scores traces using composite anomaly scoring
    4. Validates selected traces before returning

    Args:
        project_id: GCP project ID. If not provided, uses environment.
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

        # Fetch recent traces for statistical baseline
        raw_traces = list_traces(project_id, limit=50)
        traces = json.loads(raw_traces)

        if isinstance(traces, list) and len(traces) > 0 and "error" in traces[0]:
            return raw_traces

        if not traces:
            return json.dumps({"error": "No traces found in the last hour."})

        # Fetch error traces separately for hybrid selection
        error_trace_ids = set()
        if prefer_errors:
            error_traces_json = list_traces(project_id, limit=10, error_only=True)
            error_traces = json.loads(error_traces_json)
            if error_traces and not (
                isinstance(error_traces, list) and "error" in error_traces[0]
            ):
                error_trace_ids = {
                    t.get("trace_id") for t in error_traces if t.get("trace_id")
                }
                existing_ids = {t.get("trace_id") for t in traces}
                for et in error_traces:
                    if et.get("trace_id") not in existing_ids:
                        et["has_error"] = True
                        traces.append(et)

        # Extract valid traces with latencies
        valid_traces = [t for t in traces if t.get("duration_ms", 0) > 0]
        if len(valid_traces) < 2:
            return json.dumps(
                {"error": "Insufficient traces with valid duration found."}
            )

        latencies = [t["duration_ms"] for t in valid_traces]
        latencies.sort()

        # Calculate statistical metrics
        p50 = statistics.median(latencies)
        p95 = (
            latencies[int(len(latencies) * 0.95)]
            if len(latencies) > 1
            else latencies[0]
        )
        p99 = (
            latencies[int(len(latencies) * 0.99)]
            if len(latencies) > 1
            else latencies[0]
        )
        mean = statistics.mean(latencies)
        stdev = statistics.stdev(latencies) if len(latencies) > 1 else 0

        # Score all traces for anomaly detection
        for trace in valid_traces:
            has_error = (
                trace.get("has_error", False)
                or trace.get("trace_id") in error_trace_ids
            )
            trace["_anomaly_score"] = _calculate_anomaly_score(
                trace, mean, stdev, has_error
            )
            trace["_has_error"] = has_error

        # Select baseline (closest to P50, prefer no errors)
        baseline_candidates = [
            t for t in valid_traces if not t.get("_has_error", False)
        ]
        if not baseline_candidates:
            baseline_candidates = valid_traces

        baseline = min(baseline_candidates, key=lambda x: abs(x["duration_ms"] - p50))

        # Select anomaly (highest anomaly score, excluding baseline)
        anomaly_candidates = [
            t for t in valid_traces if t.get("trace_id") != baseline.get("trace_id")
        ]
        if anomaly_candidates:
            anomaly = max(anomaly_candidates, key=lambda x: x.get("_anomaly_score", 0))
        else:
            anomaly = max(valid_traces, key=lambda x: x.get("duration_ms", 0))

        # Add selection reasoning
        baseline["_selection_reason"] = f"Closest to P50 ({p50:.1f}ms)"
        anomaly_score = anomaly.get("_anomaly_score", 0)
        if anomaly.get("_has_error"):
            anomaly["_selection_reason"] = (
                f"Error trace with anomaly score {anomaly_score:.2f}"
            )
        else:
            anomaly["_selection_reason"] = (
                f"High latency anomaly score {anomaly_score:.2f}"
            )

        # Clean up internal fields
        for trace in [baseline, anomaly]:
            trace.pop("_anomaly_score", None)
            trace.pop("_has_error", None)

        validation = {
            "baseline_valid": baseline.get("trace_id") is not None,
            "anomaly_valid": anomaly.get("trace_id") is not None,
            "sample_adequate": len(valid_traces) >= min_sample_size,
            "latency_variance_detected": stdev > 0,
        }

        return json.dumps(
            {
                "stats": {
                    "count": len(valid_traces),
                    "p50_ms": round(p50, 2),
                    "p95_ms": round(p95, 2),
                    "p99_ms": round(p99, 2),
                    "mean_ms": round(mean, 2),
                    "stdev_ms": round(stdev, 2) if stdev else 0,
                    "error_traces_found": len(error_trace_ids),
                },
                "baseline": baseline,
                "anomaly": anomaly,
                "validation": validation,
                "selection_method": "hybrid_multi_signal",
            }
        )

    except Exception as e:
        error_msg = f"Failed to find example traces: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def get_trace_by_url(url: str) -> str:  # noqa: C901
    """
    Parses a Cloud Console URL to extract trace ID and fetch the trace.

    Args:
        url: The full URL from Google Cloud Console trace view.

    Returns:
        The fetched trace data as JSON.
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
            for i, part in enumerate(parts):
                if "details" in part and i + 1 < len(parts):
                    trace_id = parts[i + 1]
                    break

        # Fallback: look for hex ID in path
        if not trace_id:
            for part in reversed(parsed.path.split("/")):
                if (
                    part
                    and all(c in "0123456789abcdefABCDEF" for c in part)
                    and len(part) >= 32
                ):
                    trace_id = part
                    break

        if not project_id or not trace_id:
            return json.dumps(
                {"error": "Could not parse project_id or trace_id from URL"}
            )

        return fetch_trace(project_id, trace_id)

    except Exception as e:
        error_msg = f"Failed to get trace by URL: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
