"""Direct API client for Cloud Monitoring."""

import json
import logging
import time
from datetime import datetime, timezone

import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.cloud import monitoring_v3

from ..common import adk_tool

logger = logging.getLogger(__name__)


@adk_tool
def list_time_series(project_id: str, filter_str: str, minutes_ago: int = 60) -> str:
    """
    Lists time series data from Google Cloud Monitoring using direct API.

    Args:
        project_id: The Google Cloud Project ID.
        filter_str: The filter string to use.
        minutes_ago: The number of minutes in the past to query.

    Returns:
        A JSON string representing the list of time series.

    Example filter_str: 'metric.type="compute.googleapis.com/instance/cpu/utilization"'
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
def query_promql(project_id: str, query: str, start: str | None = None, end: str | None = None, step: str = "60s") -> str:
    """
    Executes a PromQL query using the Cloud Monitoring Prometheus API.

    Args:
        project_id: The Google Cloud Project ID.
        query: The PromQL query string.
        start: Start time in RFC3339 format (default: 1 hour ago).
        end: End time in RFC3339 format (default: now).
        step: Query resolution step (default: "60s").

    Returns:
        A JSON string containing the query results.
    """
    try:
        # Get credentials
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        session = AuthorizedSession(credentials)

        # Default time range if not provided
        if not end:
            end = datetime.now(timezone.utc).isoformat()
        if not start:
             # Default 1 hour ago
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            start_dt = datetime.fromtimestamp(end_dt.timestamp() - 3600, tz=timezone.utc)
            start = start_dt.isoformat()

        # Cloud Monitoring Prometheus API endpoint
        # https://cloud.google.com/stackdriver/docs/managed-prometheus/query
        url = f"https://monitoring.googleapis.com/v1/projects/{project_id}/location/global/prometheus/api/v1/query_range"

        params = {
            "query": query,
            "start": start,
            "end": end,
            "step": step
        }

        response = session.get(url, params=params)
        response.raise_for_status()

        return json.dumps(response.json())

    except Exception as e:
        error_msg = f"Failed to execute PromQL query: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
