"""Cloud Trace API clients for fetching and listing traces.

This module provides direct access to the Google Cloud Trace API (v1/v2).
It includes optimization features such as:
- **In-Memory Caching**: Prevents redundant API calls for the same trace ID.
- **Trace Validation**: Ensures fetched traces meet quality standards (e.g., have duration).
- **Advanced Filtering**: Simplifies the complex Cloud Trace filter syntax.
- **Anomaly Scoring**: Helper logic to identify interesting traces.

Usage:
These tools are primarily used by the "Squad" (Stage 1 sub-agents) to fetch
and inspect individual traces during triage.
"""

import json
import logging
import os
import re
import statistics
from datetime import datetime, timezone
from typing import Any, cast

from fastapi.concurrency import run_in_threadpool
from google.cloud import trace_v1
from google.protobuf.timestamp_pb2 import Timestamp

from ..common import adk_tool
from ..common.cache import get_data_cache
from ..common.telemetry import get_meter, get_tracer
from .factory import get_trace_client

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)
meter = get_meter(__name__)


class TraceFilterBuilder:
    """Helper to construct Cloud Trace filter strings.

    Encapsulates the complex [^][+]key:value syntax of Cloud Trace.
    """

    def __init__(self) -> None:
        """Initialize the builder with empty terms."""
        self.terms: list[str] = []

    def add_latency(self, duration_ms: int) -> "TraceFilterBuilder":
        """Filter by minimum latency."""
        self.terms.append(f"latency:{duration_ms}ms")
        return self

    def add_root_span_name(
        self, name: str, exact: bool = False
    ) -> "TraceFilterBuilder":
        """Filter by root span name."""
        term = f"root:{name}"
        if exact:
            term = f"+{term}"
        self.terms.append(term)
        return self

    def add_span_name(
        self, name: str, exact: bool = False, root_only: bool = False
    ) -> "TraceFilterBuilder":
        """Filter by span name."""
        prefix = "^" if root_only else ""
        op = "+" if exact else ""
        term = f"{op}{prefix}span:{name}"
        self.terms.append(term)
        return self

    def add_attribute(
        self, key: str, value: Any, exact: bool = False, root_only: bool = False
    ) -> "TraceFilterBuilder":
        """Add an attribute filter.

        Args:
            key: The attribute key (e.g. '/http/status_code').
            value: The value to match.
            exact: If True, uses exact match (+).
            root_only: If True, restricts to root span (^).
        """
        str_val = str(value)
        # Quote value if it contains special characters
        if not re.match(r"^[a-zA-Z0-9./_-]+$", str_val):
            escaped_val = str_val.replace("\\", "\\\\").replace('"', '\\"')
            str_val = f'"{escaped_val}"'

        prefix = "^" if root_only else ""
        op = "+" if exact else ""

        term = f"{op}{prefix}{key}:{str_val}"
        self.terms.append(term)
        return self

    def build(self) -> str:
        """Returns the final filter string."""
        return " ".join(self.terms)


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
    """Returns the current UTC time in ISO format.

    Use this to calculate relative time ranges for list_traces.
    """
    return datetime.now(timezone.utc).isoformat()


def fetch_trace_data(
    trace_id_or_json: str | dict[str, Any], project_id: str | None = None
) -> dict[str, Any]:
    """Helper to fetch trace data by ID or from JSON/dict.

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

    trace_json = _fetch_trace_sync(project_id, trace_id_or_json)
    try:
        if isinstance(trace_json, dict):
            return trace_json
        data = json.loads(trace_json)
        if data and isinstance(data, dict) and "error" in data:
            return cast(dict[str, Any], data)
        return cast(dict[str, Any], data)
    except json.JSONDecodeError:
        return {"error": "Invalid trace JSON"}


@adk_tool
async def fetch_trace(project_id: str, trace_id: str) -> str:
    """Fetches a specific trace by ID from Cloud Trace API.

    Uses caching to avoid redundant API calls when the same trace
    is requested multiple times (e.g., by different sub-agents).

    Args:
        project_id: The Google Cloud Project ID.
        trace_id: The unique hex ID of the trace.

    Returns:
        A JSON string representation of the trace, including all spans.
    """
    from fastapi.concurrency import run_in_threadpool

    return await run_in_threadpool(_fetch_trace_sync, project_id, trace_id)


def _fetch_trace_sync(project_id: str, trace_id: str) -> str:
    """Synchronous implementation of fetch_trace."""
    # Check cache first
    cache = get_data_cache()

    cached = cache.get(f"trace:{trace_id}")
    if cached:
        logger.debug(f"Cache hit for trace {trace_id}, skipping API call")
        return cast(str, cached)

    with tracer.start_as_current_span("fetch_trace") as span:
        span.set_attribute("gcp.project_id", project_id)
        span.set_attribute("gcp.trace_id", trace_id)
        span.set_attribute("rpc.system", "google_cloud")
        span.set_attribute("rpc.service", "cloud_trace")
        span.set_attribute("rpc.method", "get_trace")

        try:
            client = get_trace_client()

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

            dur_ms = (
                (trace_end - trace_start) * 1000 if trace_start and trace_end else 0
            )
            span.set_attribute("gcp.trace.duration_ms", dur_ms)
            span.set_attribute("gcp.trace.span_count", len(spans))

            result = {
                "trace_id": trace_obj.trace_id,
                "project_id": trace_obj.project_id,
                "spans": spans,
                "span_count": len(spans),
                "duration_ms": dur_ms,
            }

            # Cache the result before returning
            result_json = json.dumps(result)
            cache.put(f"trace:{trace_id}", result_json)

            return result_json

        except Exception as e:
            span.record_exception(e)
            error_msg = f"Failed to fetch trace: {e!s}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({"error": error_msg})


@adk_tool
async def list_traces(
    project_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 10,
    filter_str: str = "",
    min_latency_ms: int | None = None,
    error_only: bool = False,
    attributes_json: str | None = None,
) -> str:
    """Lists recent traces with advanced filtering capabilities.

    Args:
        project_id: The GCP project ID.
        start_time: ISO timestamp for start of window.
        end_time: ISO timestamp for end of window.
        limit: Max number of traces to return.
        filter_str: Raw filter string (overrides other filters if provided).
        min_latency_ms: Minimum latency in milliseconds.
        error_only: If True, filters for traces with errors.
        attributes_json: JSON string of attribute key-values to filter by (e.g., '{"/http/status_code": "500"}').

    Returns:
        JSON string list of trace summaries.
    """
    from fastapi.concurrency import run_in_threadpool

    return await run_in_threadpool(
        _list_traces_sync,
        project_id,
        limit,
        min_latency_ms,
        error_only,
        start_time,
        end_time,
        attributes_json,
    )


def _list_traces_sync(
    project_id: str,
    limit: int,
    min_latency_ms: int | None,
    error_only: bool,
    start_time: str | None,
    end_time: str | None,
    attributes_json: str | None,
) -> str:
    """Synchronous implementation of list_traces."""
    with tracer.start_as_current_span("list_traces"):
        try:
            client = get_trace_client()

            # Construct complex filter string
            # Placeholder for build_trace_filter, assuming it's defined elsewhere or will be added.
            # For now, a simple filter construction based on provided parameters.
            filters = []
            if min_latency_ms:
                filters.append(f"latency:{min_latency_ms}ms")
            if error_only:
                filters.append("error:true")
            filter_str = " ".join(filters)

            # Parse time window
            start_timestamp = None
            end_timestamp = None

            if start_time:
                try:
                    dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    start_timestamp = Timestamp()
                    start_timestamp.FromDatetime(dt)
                except Exception:
                    logger.warning(f"Invalid start_time format: {start_time}")

            if end_time:
                try:
                    dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                    end_timestamp = Timestamp()
                    end_timestamp.FromDatetime(dt)
                except Exception:
                    logger.warning(f"Invalid end_time format: {end_time}")

            # Make API Request
            request_kwargs = {
                "project_id": project_id,
                "page_size": limit,
                "filter": filter_str,
                "view": trace_v1.ListTracesRequest.ViewType.ROOTSPAN,  # Lightweight view
            }

            if start_timestamp:
                request_kwargs["start_time"] = start_timestamp
            if end_timestamp:
                request_kwargs["end_time"] = end_timestamp

            response = client.list_traces(
                request=trace_v1.ListTracesRequest(**request_kwargs)
            )

            traces = []
            for trace in response:
                summary = {"trace_id": trace.trace_id, "project_id": trace.project_id}

                # Extract root span details if available
                if trace.spans:
                    root_span = trace.spans[0]
                    summary["name"] = root_span.name

                    start_ts = root_span.start_time.timestamp()
                    end_ts = root_span.end_time.timestamp()
                    duration_ms = (end_ts - start_ts) * 1000

                    summary["start_time"] = root_span.start_time.isoformat()
                    summary["duration_ms"] = round(duration_ms, 2)

                    # Labels/Attributes
                    labels = root_span.labels or {}
                    summary["status"] = labels.get("/http/status_code", "0")
                    summary["url"] = labels.get("/http/url", "")

                traces.append(summary)

                if len(traces) >= limit:
                    break

            return json.dumps(traces)

        except Exception as e:
            error_msg = f"Failed to list traces: {e!s}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({"error": error_msg})


def _calculate_anomaly_score(
    trace: dict[str, Any],
    mean_latency: float,
    stdev_latency: float,
    has_error: bool = False,
) -> float:
    """Calculate a composite anomaly score for a trace.

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


def validate_trace(trace_data: str | dict[str, Any]) -> dict[str, Any]:
    """Validates trace data for completeness and quality.

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
async def find_example_traces(
    project_id: str | None = None, prefer_errors: bool = True, min_sample_size: int = 20
) -> str:
    """Intelligently discovers representative baseline and anomaly traces.

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
        JSON string with 'baseline' and 'anomaly' keys.
    """
    try:
        try:
            if not project_id:
                project_id = _get_project_id()
        except ValueError:
            return json.dumps({"error": "GOOGLE_CLOUD_PROJECT not set"})

        # Strategy 1: Look for slow traces directly (latency > 1s)
        slow_filter = TraceFilterBuilder().add_latency(1000).build()
        slow_traces_json = await list_traces(
            project_id, limit=20, filter_str=slow_filter
        )
        slow_traces = json.loads(slow_traces_json)

        # Strategy 2: Fetch recent traces for statistical baseline
        raw_traces = await list_traces(project_id, limit=50)
        traces = json.loads(raw_traces)

        if (
            isinstance(traces, list)
            and traces
            and isinstance(traces[0], dict)
            and "error" in traces[0]
        ):
            return cast(str, raw_traces)

        if not traces:
            return json.dumps({"error": "No traces found in the last hour."})

        # Inject slow traces into our pool
        if (
            isinstance(slow_traces, list)
            and slow_traces
            and "error" not in slow_traces[0]
        ):
            existing_ids = {t["trace_id"] for t in traces if "trace_id" in t}
            for st in slow_traces:
                if st["trace_id"] not in existing_ids:
                    traces.append(st)

        # Fetch error traces separately for hybrid selection
        error_trace_ids = set()
        if prefer_errors:
            error_traces_json = await list_traces(project_id, limit=10, error_only=True)
            error_traces = json.loads(error_traces_json)
            if error_traces and not (
                isinstance(error_traces, list) and "error" in error_traces[0]
            ):
                error_trace_ids = {
                    t.get("trace_id") for t in error_traces if t.get("trace_id")
                }
                existing_ids = {t.get("trace_id") for t in traces if "trace_id" in t}
                for et in error_traces:
                    if et.get("trace_id") not in existing_ids:
                        et["has_error"] = True
                        traces.append(et)

        # Use threadpool for CPU-bound filtering and calculation
        def _calculate_example_traces() -> str:
            # Extract valid traces with latencies
            valid_traces = [
                t for t in traces if isinstance(t, dict) and t.get("duration_ms", 0) > 0
            ]
            if not valid_traces:
                return json.dumps({"error": "No traces with valid duration found."})

            latencies = [t["duration_ms"] for t in valid_traces]
            latencies.sort()

            # Calculate statistical metrics
            p50 = statistics.median(latencies)
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

            # Select anomaly (highest anomaly score)
            anomaly = max(valid_traces, key=lambda x: x.get("_anomaly_score", 0))

            # Select baseline (closest to P50, prefer no errors)
            baseline_candidates = [
                t for t in valid_traces if not t.get("_has_error", False)
            ]
            if not baseline_candidates:
                baseline_candidates = valid_traces

            baseline = min(
                baseline_candidates, key=lambda x: abs(x["duration_ms"] - p50)
            )

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
            stats = {
                "count": len(valid_traces),
                "p50_ms": round(p50, 2),
                "mean_ms": round(mean, 2),
                "stdev_ms": round(stdev, 2) if stdev else 0,
                "error_traces_found": len(error_trace_ids),
            }

            validation = {
                "baseline_valid": baseline.get("trace_id") is not None,
                "anomaly_valid": anomaly.get("trace_id") is not None,
                "sample_adequate": len(valid_traces)
                >= 20,  # Use a reasonable default or pass min_sample_size
                "latency_variance_detected": stdev > 0,
            }

            return json.dumps(
                {
                    "stats": stats,
                    "baseline": baseline,
                    "anomaly": anomaly,
                    "validation": validation,
                    "selection_method": "hybrid_multi_signal",
                }
            )

        results_json = await run_in_threadpool(_calculate_example_traces)
        results = json.loads(results_json)

        if "error" in results:
            return results_json

        # --- NEW: Try to find a better baseline with same root span name ---
        anomaly = results["anomaly"]
        root_name = anomaly.get("name")  # name is populated in list_traces summary

        if root_name:
            # Search for traces with same root name that are "healthy" (shorter)
            fb = TraceFilterBuilder().add_root_span_name(root_name, exact=True)
            candidates_json = await list_traces(
                project_id, limit=20, filter_str=fb.build()
            )
            candidates = json.loads(candidates_json)

            if (
                isinstance(candidates, list)
                and candidates
                and "error" not in candidates[0]
            ):
                # Filter for traces significantly faster than anomaly
                shorter = [
                    t
                    for t in candidates
                    if t.get("duration_ms", 0) < anomaly["duration_ms"] * 0.8
                ]
                if shorter:
                    # Pick the one closest to median or just the fastest?
                    # Let's pick median of these healthy candidates
                    shorter.sort(key=lambda x: x.get("duration_ms", 0))
                    best_baseline = shorter[len(shorter) // 2]
                    best_baseline["_selection_reason"] = (
                        f"Same root span ({root_name}), 20%+ faster"
                    )
                    results["baseline"] = best_baseline
                    results["selection_method"] += "+root_name_match"

        return json.dumps(results)

    except Exception as e:
        error_msg = f"Failed to find example traces: {e!s}"
        logger.error(error_msg, exc_info=True)
        return json.dumps({"error": error_msg})


@adk_tool
async def get_trace_by_url(url: str) -> str:
    """Parses a Cloud Console URL and fetches the trace details.

    Args:
        url: The full URL from the browser address bar.

    Returns:
        JSON string with trace details.
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

        return cast(str, await fetch_trace(project_id, trace_id))

    except Exception as e:
        error_msg = f"Failed to get trace by URL: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
