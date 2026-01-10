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
def list_log_entries(project_id: str, filter_str: str, limit: int = 10, page_token: str | None = None) -> str:
    """
    Lists log entries from Google Cloud Logging using direct API.

    Args:
        project_id: The Google Cloud Project ID.
        filter_str: The filter string to use.
        limit: The maximum number of log entries to return.
        page_token: Token for the next page of results.

    Returns:
        A JSON string containing:
        - "entries": List of log entries.
        - "next_page_token": Token for the next page (if any).

    Example filter_str: 'resource.type="gce_instance" AND severity="ERROR"'
    """
    try:
        client = LoggingServiceV2Client()
        resource_names = [f"projects/{project_id}"]
        
        # Ensure timestamp desc ordering for recent logs
        order_by = "timestamp desc"
        
        request = {
            "resource_names": resource_names,
            "filter": filter_str,
            "page_size": limit,
            "order_by": order_by,
        }
        if page_token:
            request["page_token"] = page_token

        # Get the iterator/pager
        entries_pager = client.list_log_entries(request=request)
        
        # Fetch a single page to respect limit and get token
        # We use .pages iterator to get the first page object
        results = []
        next_token = None
        
        # Get the first page of the iterator
        pages_iterator = entries_pager.pages
        first_page = next(pages_iterator, None)
        
        if first_page:
            for entry in first_page:
                # Handle payload fields safely
                payload_data = None
                # Check for standard payload fields in GAPIC objects
                if entry.text_payload:
                    payload_data = entry.text_payload
                elif hasattr(entry, "json_payload") and entry.json_payload:
                    # Convert Proto Struct/Map to dict
                    # Note: accessing attributes on json_payload might be needed depending on proto version
                    # But usually dict(entry.json_payload) or direct conversion works for Struct
                    try:
                        # Attempt to serialize or convert
                        import google.protobuf.json_format
                        # Struct can be complex, often just casting to dict works if it's a MapComposite
                        # But safely we can use the helper if available, or just repr if all else fails
                        # Actually, for simple usage:
                        payload_data = dict(entry.json_payload)
                    except (ValueError, TypeError):
                        payload_data = str(entry.json_payload)
                elif hasattr(entry, "proto_payload") and entry.proto_payload:
                    payload_data = f"[ProtoPayload] {entry.proto_payload.type_url}"
                else:
                    payload_data = ""

                # Truncate if string and too long
                if isinstance(payload_data, str) and len(payload_data) > 2000:
                   payload_data = payload_data[:2000] + "...(truncated)"

                results.append(
                    {
                        "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                        "severity": entry.severity.name,
                        "payload": payload_data,
                        "resource": {
                            "type": entry.resource.type,
                            "labels": dict(entry.resource.labels),
                        },
                        "insert_id": entry.insert_id,
                    }
                )
            next_token = first_page.next_page_token

        return json.dumps({
            "entries": results,
            "next_page_token": next_token or None
        })
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
