"""Direct API clients for GCP observability services.

These tools use direct GCP client libraries. They are useful as fallbacks
when MCP is unavailable or for simple queries that don't need MCP features.
"""

import json
import logging
import time
from datetime import datetime, timezone

from google.cloud import monitoring_v3
from google.cloud.logging_v2.services.logging_service_v2 import LoggingServiceV2Client

from ..common import adk_tool

logger = logging.getLogger(__name__)


@adk_tool
def list_log_entries(project_id: str, filter_str: str, limit: int = 10) -> str:
    """
    Lists log entries from Google Cloud Logging using direct API.

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
def list_error_events(project_id: str, minutes_ago: int = 60) -> str:
    """
    Lists error events from Google Cloud Error Reporting using direct API.

    Args:
        project_id: The Google Cloud Project ID.
        minutes_ago: The number of minutes in the past to query.

    Returns:
        A JSON string representing the list of error events.
    """
    try:
        import google.cloud.errorreporting_v1beta1 as errorreporting_v1beta1

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
    Use this to calculate relative time ranges (e.g., 'now - 1 hour') for queries.
    """
    return datetime.now(timezone.utc).isoformat()
