"""Direct API client for Cloud Monitoring.

This module provides tools for fetching metrics via the Cloud Monitoring API.
It allows the agent to:
- List time series data (raw metrics).
- Execute PromQL queries (Managed Prometheus).

It is used primarily by the `metrics_analyzer` sub-agent to correlate metric spikes
with trace data using Exemplars.
"""

import json
import logging
import time
from datetime import datetime, timezone

import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.cloud import monitoring_v3

from ..common import adk_tool
from ..common.telemetry import get_tracer
from .factory import get_monitoring_client

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


@adk_tool
async def list_time_series(
    project_id: str, filter_str: str, minutes_ago: int = 60
) -> str:
    """Lists time series data from Google Cloud Monitoring using direct API.

    IMPORTANT: You must use valid combinations of metric and monitored resource labels.
    - For GCE Instances (`gce_instance`), valid labels are `instance_id`, `zone`, `project_id`.
      DO NOT use `service_name` or `service` with GCE metrics.
    - For GKE Containers (`k8s_container`), valid labels are `namespace_name`, `pod_name`, `container_name`, `cluster_name`.
    - To filter by service, use `query_promql` instead with a PromQL query like `metric{service="service-name"}`.

    Args:
        project_id: The Google Cloud Project ID.
        filter_str: The filter string to use.
        minutes_ago: The number of minutes in the past to query.

    Returns:
        A JSON string representing the list of time series.

    Example filter_str: 'metric.type="compute.googleapis.com/instance/cpu/utilization" AND resource.labels.instance_id="123456789"'
    """
    from fastapi.concurrency import run_in_threadpool

    return await run_in_threadpool(
        _list_time_series_sync, project_id, filter_str, minutes_ago
    )


def _list_time_series_sync(
    project_id: str, filter_str: str, minutes_ago: int = 60
) -> str:
    """Synchronous implementation of list_time_series."""
    with tracer.start_as_current_span("list_time_series") as span:
        span.set_attribute("gcp.project_id", project_id)
        span.set_attribute("gcp.monitoring.filter", filter_str)
        span.set_attribute("rpc.system", "google_cloud")
        span.set_attribute("rpc.service", "cloud_monitoring")
        span.set_attribute("rpc.method", "list_time_series")

        try:
            client = get_monitoring_client()
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
                view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,  # type: ignore
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
            span.set_attribute("gcp.monitoring.series_count", len(time_series_data))
            return json.dumps(time_series_data)
        except Exception as e:
            span.record_exception(e)
            error_str = str(e)

            # Suggest fixes for common filter errors
            suggestion = ""
            if (
                "400" in error_str
                and "service" in filter_str
                and "compute" in filter_str
            ):
                suggestion = (
                    ". HINT: 'resource.labels.service_name' is NOT valid for GCE metrics. "
                    "Use 'resource.labels.instance_id' or use query_promql() to filter/aggregate by service."
                )

            error_msg = f"Failed to list time series: {error_str}{suggestion}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({"error": error_msg})


@adk_tool
async def query_promql(
    project_id: str,
    query: str,
    start: str | None = None,
    end: str | None = None,
    step: str = "60s",
) -> str:
    """Executes a PromQL query using the Cloud Monitoring Prometheus API.

    Args:
        project_id: The Google Cloud Project ID.
        query: The PromQL query string.
        start: Start time in RFC3339 format (default: 1 hour ago).
        end: End time in RFC3339 format (default: now).
        step: Query resolution step (default: "60s").

    Returns:
        A JSON string containing the query results.
    """
    from fastapi.concurrency import run_in_threadpool

    return await run_in_threadpool(
        _query_promql_sync, project_id, query, start, end, step
    )


def _query_promql_sync(
    project_id: str,
    query: str,
    start: str | None = None,
    end: str | None = None,
    step: str = "60s",
) -> str:
    """Synchronous implementation of query_promql."""
    try:
        # Get credentials
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        session = AuthorizedSession(credentials)  # type: ignore[no-untyped-call]

        # Default time range if not provided
        if not end:
            end = datetime.now(timezone.utc).isoformat()
        if not start:
            # Default 1 hour ago
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            start_dt = datetime.fromtimestamp(
                end_dt.timestamp() - 3600, tz=timezone.utc
            )
            start = start_dt.isoformat()

        # Cloud Monitoring Prometheus API endpoint
        # https://cloud.google.com/stackdriver/docs/managed-prometheus/query
        url = f"https://monitoring.googleapis.com/v1/projects/{project_id}/location/global/prometheus/api/v1/query_range"

        params = {"query": query, "start": start, "end": end, "step": step}

        response = session.get(url, params=params)
        response.raise_for_status()

        return json.dumps(response.json())

    except Exception as e:
        error_msg = f"Failed to execute PromQL query: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
