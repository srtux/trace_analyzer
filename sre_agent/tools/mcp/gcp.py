"""MCP (Model Context Protocol) integration for GCP services.

This module provides lazy-loaded MCP toolsets for GCP observability services:
- BigQuery: SQL-based data analysis
- Cloud Logging: Log queries and analysis
- Cloud Monitoring: Metrics and time series queries

MCP toolsets are created lazily in async context to avoid session lifecycle issues.
Creating at module import time causes "Attempted to exit cancel scope in a
different task" errors because anyio cancel scopes cannot cross task boundaries.
"""

import asyncio
import logging
import os
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import google.auth
import httpx
from google.adk.tools import ToolContext  # type: ignore[attr-defined]
from google.adk.tools.api_registry import ApiRegistry

from ...schema import ToolStatus
from ..common import adk_tool
from .mock_mcp import MockMcpToolset

logger = logging.getLogger(__name__)


def get_project_id_with_fallback() -> str | None:
    """Get project ID from environment or default credentials."""
    project_id = None
    try:
        _, project_id = google.auth.default()
        project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
    except Exception:
        pass
    return project_id


def create_bigquery_mcp_toolset(project_id: str | None = None) -> Any:
    """Creates a new instance of the BigQuery MCP toolset.

    NOTE: This function should be called in an async context (within an async
    function) to ensure proper MCP session lifecycle management.

    Tools exposed:
        - execute_sql: Execute SQL queries
        - list_dataset_ids: List available datasets
        - list_table_ids: List tables in a dataset
        - get_table_info: Get table schema and metadata

    Environment variable override:
        BIGQUERY_MCP_SERVER: Override the default MCP server

    Args:
        project_id: GCP project ID. If not provided, uses default credentials.

    Returns:
        MCP toolset or None if unavailable.
    """
    if not project_id:
        project_id = get_project_id_with_fallback()

    if not project_id:
        logger.warning(
            "No Project ID detected; BigQuery MCP toolset will not be available"
        )
        return None

    try:
        logger.info(f"Creating BigQuery MCP toolset for project: {project_id}")

        default_server = "google-bigquery.googleapis.com-mcp"
        mcp_server = os.environ.get("BIGQUERY_MCP_SERVER", default_server)
        mcp_server_name = (
            f"projects/{project_id}/locations/global/mcpServers/{mcp_server}"
        )

        api_registry = ApiRegistry(
            project_id, header_provider=lambda _: {"x-goog-user-project": project_id}
        )

        mcp_toolset = api_registry.get_toolset(
            mcp_server_name=mcp_server_name,
            tool_filter=[
                "execute_sql",
                "list_dataset_ids",
                "list_table_ids",
                "get_table_info",
            ],
        )

        return mcp_toolset

    except Exception as e:
        logger.error(f"Failed to create BigQuery MCP toolset: {e}")
        logger.info("Falling back to Mock BigQuery MCP toolset")
        return MockMcpToolset()


def create_logging_mcp_toolset(project_id: str | None = None) -> Any:
    """Creates a Cloud Logging MCP toolset with generic logging capabilities.

    Tools exposed:
        - list_log_entries: Search and retrieve log entries

    Environment variable override:
        LOGGING_MCP_SERVER: Override the default MCP server

    Args:
        project_id: GCP project ID. If not provided, uses default credentials.

    Returns:
        MCP toolset or None if unavailable.
    """
    if not project_id:
        project_id = get_project_id_with_fallback()

    if not project_id:
        logger.warning(
            "No Project ID detected; Cloud Logging MCP toolset will not be available"
        )
        return None

    try:
        logger.info(f"Creating Cloud Logging MCP toolset for project: {project_id}")

        default_server = "logging.googleapis.com-mcp"
        mcp_server = os.environ.get("LOGGING_MCP_SERVER", default_server)
        mcp_server_name = (
            f"projects/{project_id}/locations/global/mcpServers/{mcp_server}"
        )

        api_registry = ApiRegistry(
            project_id, header_provider=lambda _: {"x-goog-user-project": project_id}
        )

        mcp_toolset = api_registry.get_toolset(
            mcp_server_name=mcp_server_name,
            tool_filter=["list_log_entries"],
        )

        return mcp_toolset

    except Exception as e:
        logger.error(f"Failed to create Cloud Logging MCP toolset: {e}")
        logger.info("Falling back to Mock Cloud Logging MCP toolset")
        return MockMcpToolset()


def create_monitoring_mcp_toolset(project_id: str | None = None) -> Any:
    """Creates a Cloud Monitoring MCP toolset with generic metrics capabilities.

    Tools exposed:
        - list_timeseries: Query time series metrics data
        - query_range: Evaluate PromQL queries over a time range

    Environment variable override:
        MONITORING_MCP_SERVER: Override the default MCP server

    Args:
        project_id: GCP project ID. If not provided, uses default credentials.

    Returns:
        MCP toolset or None if unavailable.
    """
    if not project_id:
        project_id = get_project_id_with_fallback()

    if not project_id:
        logger.warning(
            "No Project ID detected; Cloud Monitoring MCP toolset will not be available"
        )
        return None

    try:
        logger.info(f"Creating Cloud Monitoring MCP toolset for project: {project_id}")

        default_server = "monitoring.googleapis.com-mcp"
        mcp_server = os.environ.get("MONITORING_MCP_SERVER", default_server)
        mcp_server_name = (
            f"projects/{project_id}/locations/global/mcpServers/{mcp_server}"
        )

        api_registry = ApiRegistry(
            project_id, header_provider=lambda _: {"x-goog-user-project": project_id}
        )

        mcp_toolset = api_registry.get_toolset(
            mcp_server_name=mcp_server_name,
            tool_filter=["list_timeseries", "query_range"],
        )

        return mcp_toolset

    except Exception as e:
        logger.error(f"Failed to create Cloud Monitoring MCP toolset: {e}")
        logger.info("Falling back to Mock Cloud Monitoring MCP toolset")
        return MockMcpToolset()


async def call_mcp_tool_with_retry(
    create_toolset_fn: Callable[[str | None], Any],
    tool_name: str,
    args: dict[str, Any],
    tool_context: ToolContext,
    project_id: str | None = None,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> dict[str, Any]:
    """Generic helper to call an MCP tool with retry logic for session errors.

    Args:
        create_toolset_fn: Function to create the MCP toolset.
        tool_name: Name of the MCP tool to call.
        args: Arguments to pass to the tool.
        tool_context: ADK tool context.
        project_id: Optional project ID override.
        max_retries: Max retry attempts for session errors.
        base_delay: Base delay for exponential backoff.

    Returns:
        Tool result or error dict.
    """
    from fastapi.concurrency import run_in_threadpool

    if not project_id:
        project_id = get_project_id_with_fallback()

    if not project_id:
        return {
            "status": ToolStatus.ERROR,
            "error": "No project ID available. Set GOOGLE_CLOUD_PROJECT environment variable.",
        }

    for attempt in range(max_retries):
        mcp_toolset = None
        try:
            logger.debug(
                f"DEBUG: Calling create_toolset_fn for {tool_name} (project_id={project_id})"
            )
            # Offload blocking synchronous toolset creation to threadpool
            # Wrap in timeout to prevent hanging during initialization
            try:
                mcp_toolset = await asyncio.wait_for(
                    run_in_threadpool(create_toolset_fn, project_id),
                    timeout=15.0,  # 15s timeout for toolset creation
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout creating MCP toolset for {tool_name}")
                return {
                    "status": ToolStatus.ERROR,
                    "error": (
                        f"Failed to create MCP toolset for '{tool_name}': Connection timed out after 15 seconds. "
                        "The MCP server may be unavailable or overloaded. DO NOT retry this tool. "
                        "Use direct API alternatives instead: list_log_entries for logs, fetch_trace for traces, "
                        "query_promql for metrics."
                    ),
                    "non_retryable": True,
                    "error_type": "MCP_CONNECTION_TIMEOUT",
                }

            logger.debug(f"DEBUG: create_toolset_fn returned for {tool_name}")

            if not mcp_toolset:
                return {
                    "status": ToolStatus.ERROR,
                    "error": (
                        f"MCP toolset unavailable for '{tool_name}'. The MCP server could not be initialized. "
                        "This is typically a configuration or authentication issue. DO NOT retry this tool. "
                        "Use direct API alternatives instead: list_log_entries for logs, fetch_trace for traces, "
                        "query_promql or list_time_series for metrics."
                    ),
                    "non_retryable": True,
                    "error_type": "MCP_UNAVAILABLE",
                }

            tools = await mcp_toolset.get_tools()

            for tool in tools:
                if tool.name == tool_name:
                    # Enforce timeout on tool execution
                    try:
                        result = await asyncio.wait_for(
                            tool.run_async(args=args, tool_context=tool_context),
                            timeout=30.0,  # 30s timeout for tool execution
                        )
                        return {
                            "status": ToolStatus.SUCCESS,
                            "result": result,
                            "metadata": {"source": "mcp"},
                        }
                    except asyncio.TimeoutError:
                        logger.error(f"Timeout executing MCP tool {tool_name}")
                        return {
                            "status": ToolStatus.ERROR,
                            "error": (
                                f"Tool '{tool_name}' timed out after 30 seconds. This is typically caused by "
                                "slow network conditions or high server load. DO NOT retry immediately. "
                                "Consider using direct API alternatives (list_log_entries, fetch_trace, query_promql) "
                                "which may be more reliable, or wait and try again later."
                            ),
                            "non_retryable": True,
                            "error_type": "TIMEOUT",
                        }
                    except asyncio.CancelledError:
                        logger.warning(f"Tool execution cancelled for {tool_name}")
                        # Return a specific error status for cancellation instead of raising
                        # This prevents the evaluation framework from crashing with a traceback
                        # IMPORTANT: Include guidance to prevent retry loops
                        return {
                            "status": ToolStatus.ERROR,
                            "error": (
                                f"Tool '{tool_name}' execution was cancelled by the system due to "
                                "resource constraints or timeout. This is a non-retryable system error. "
                                "DO NOT retry this tool. Instead, try an alternative approach: "
                                "use direct API tools (like list_log_entries, fetch_trace) instead of MCP-based tools, "
                                "or ask the user to check their infrastructure."
                            ),
                            "non_retryable": True,
                            "error_type": "SYSTEM_CANCELLATION",
                        }

            return {
                "status": ToolStatus.ERROR,
                "error": (
                    f"Tool '{tool_name}' not found in MCP toolset. This is a configuration error - "
                    "the tool may not be available in the current MCP server. DO NOT retry. "
                    "Use direct API alternatives instead."
                ),
                "non_retryable": True,
                "error_type": "TOOL_NOT_FOUND",
            }

        except (httpx.HTTPStatusError, Exception) as e:
            logger.error(
                f"MCP Tool execution failed: {tool_name} error={e!s}", exc_info=True
            )
            if hasattr(e, "response") and hasattr(e.response, "text"):
                logger.error(f"HTTP Response Body: {e.response.text}")

            error_str = str(e)
            is_session_error = "Session terminated" in error_str or (
                "session" in error_str.lower() and "error" in error_str.lower()
            )

            if is_session_error and attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                logger.warning(
                    f"MCP session error during {tool_name} attempt {attempt + 1}/{max_retries}: {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
            elif is_session_error and attempt >= max_retries - 1:
                # Session errors exhausted all retries - mark as non-retryable
                logger.error(
                    f"{tool_name} failed after {max_retries} attempts due to session errors: {e}"
                )
                return {
                    "status": ToolStatus.ERROR,
                    "error": (
                        f"Tool '{tool_name}' failed after {max_retries} retry attempts due to persistent session errors. "
                        "The MCP connection is unstable. DO NOT retry this tool. "
                        "Switch to direct API alternatives: list_log_entries, fetch_trace, query_promql, list_time_series."
                    ),
                    "non_retryable": True,
                    "error_type": "MAX_RETRIES_EXHAUSTED",
                }
            else:
                # Non-session error - determine if retryable based on error content
                error_str_lower = str(e).lower()
                is_auth_error = any(
                    kw in error_str_lower
                    for kw in ["permission", "unauthorized", "forbidden", "403", "401"]
                )
                is_not_found = any(
                    kw in error_str_lower
                    for kw in ["not found", "404", "does not exist"]
                )
                is_non_retryable = is_auth_error or is_not_found

                return {
                    "status": ToolStatus.ERROR,
                    "error": (
                        f"Tool '{tool_name}' execution failed: {e!s}. "
                        + (
                            "This appears to be a permission or resource issue - DO NOT retry. "
                            "Check authentication and resource availability."
                            if is_non_retryable
                            else "This may be a transient error. If the issue persists after one retry, "
                            "try using direct API alternatives instead."
                        )
                    ),
                    "non_retryable": is_non_retryable,
                    "error_type": "AUTH_ERROR"
                    if is_auth_error
                    else "NOT_FOUND"
                    if is_not_found
                    else "EXECUTION_ERROR",
                }
        finally:
            if mcp_toolset and hasattr(mcp_toolset, "close"):
                try:
                    await mcp_toolset.close()
                except asyncio.CancelledError:
                    # Ignore cancellation errors during cleanup to ensure result is returned
                    logger.debug(
                        "MCP toolset close interrupted by cancellation (ignored)"
                    )
                except RuntimeError as e:
                    # Ignore "Attempted to exit cancel scope..." errors from anyio/mcp cleanup
                    # These occur due to task scoping issues in the underlying library during forced cleanup
                    logger.debug(f"RuntimeError during MCP cleanup (ignored): {e}")
                except Exception as e:
                    logger.warning(f"Error closing MCP toolset: {e}")

    return {
        "status": ToolStatus.ERROR,
        "error": (
            f"Tool '{tool_name}' failed after {max_retries} retry attempts due to persistent session errors. "
            "The MCP connection is unstable. DO NOT retry this tool. "
            "Switch to direct API alternatives: list_log_entries, fetch_trace, query_promql, list_time_series."
        ),
        "non_retryable": True,
        "error_type": "MAX_RETRIES_EXHAUSTED",
    }


# =============================================================================
# Generic GCP MCP Tools
# =============================================================================


@adk_tool
async def mcp_list_log_entries(
    filter: str,
    project_id: str | None = None,
    page_size: int = 100,
    order_by: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Search and retrieve log entries from Google Cloud Logging via MCP.

    This is the primary tool for querying Cloud Logging. Use it for debugging
    application behavior, finding specific error messages, auditing events,
    or any log analysis task.

    Args:
        filter: Cloud Logging filter expression. Powerful syntax for selecting logs
            by severity, resource type, text content, labels, and more.
        project_id: GCP project ID. If not provided, uses default credentials.
        page_size: Maximum number of log entries to return (default 100).
        order_by: Optional field to sort by (e.g., "timestamp desc").
        tool_context: ADK tool context (required).

    Returns:
        Log entries matching the filter criteria.

    Example filters:
        - 'severity>=ERROR' - All errors and above
        - 'resource.type="k8s_container"' - Kubernetes container logs
        - 'resource.type="gce_instance"' - Compute Engine logs
        - 'textPayload:"OutOfMemory"' - Logs containing specific text
        - 'jsonPayload.level="error"' - Structured logs by field
        - 'trace="projects/PROJECT/traces/TRACE_ID"' - Logs for a trace
        - 'timestamp>="2024-01-01T00:00:00Z"' - Time-bounded queries
        - 'labels.env="production" AND severity>=WARNING' - Combined filters
    """
    if tool_context is None:
        raise ValueError("tool_context is required for MCP tools")

    args = {
        "filter": filter,
        "page_size": page_size,
    }
    if order_by:
        args["order_by"] = order_by

    # Add resource_names if project_id is available
    pid = project_id or get_project_id_with_fallback()
    if pid:
        args["resource_names"] = [f"projects/{pid}"]

    return await call_mcp_tool_with_retry(
        create_logging_mcp_toolset,
        "list_log_entries",
        args,
        tool_context,
        project_id=project_id,
    )


@adk_tool
async def mcp_list_timeseries(
    filter: str,
    project_id: str | None = None,
    interval_start_time: str | None = None,
    interval_end_time: str | None = None,
    minutes_ago: int = 60,
    aggregation_json: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Query time series metrics data from Google Cloud Monitoring via MCP.

    Use this tool to retrieve metric values over time for monitoring, alerting,
    capacity planning, performance analysis, or any metrics-based task.

    Args:
        filter: Monitoring filter string for selecting metrics and resources.
        project_id: GCP project ID. If not provided, uses default credentials.
        interval_start_time: Start of time interval (ISO format). If not provided,
            calculated from minutes_ago.
        interval_end_time: End of time interval (ISO format). If not provided,
            uses current time.
        minutes_ago: Minutes back from now for start time (default 60). Only used
            if interval_start_time is not provided.
        aggregation_json: Optional aggregation settings as JSON string (e.g., '{"alignmentPeriod": "60s", ...}').
        tool_context: ADK tool context (required).

    Returns:
        Time series data with metric values, labels, and timestamps.

    Example filters:
        - 'metric.type="compute.googleapis.com/instance/cpu/utilization"' - CPU usage
        - 'metric.type="loadbalancing.googleapis.com/https/request_count"' - LB requests
        - 'metric.type="cloudsql.googleapis.com/database/cpu/utilization"' - Cloud SQL CPU
        - 'resource.labels.instance_id="12345"' - Filter by instance
        - 'metric.labels.response_code="500"' - Filter by metric label
    """
    if tool_context is None:
        raise ValueError("tool_context is required for MCP tools")

    import json
    import time as time_module

    pid = project_id or get_project_id_with_fallback()

    # Build time interval
    if interval_end_time:
        end_dt = datetime.fromisoformat(interval_end_time.replace("Z", "+00:00"))
        end_seconds = int(end_dt.timestamp())
    else:
        end_seconds = int(time_module.time())

    if interval_start_time:
        start_dt = datetime.fromisoformat(interval_start_time.replace("Z", "+00:00"))
        start_seconds = int(start_dt.timestamp())
    else:
        start_seconds = end_seconds - (minutes_ago * 60)

    args = {
        "name": f"projects/{pid}" if pid else "",
        "filter": filter,
        "interval": {
            "end_time": {"seconds": end_seconds},
            "start_time": {"seconds": start_seconds},
        },
    }

    if aggregation_json:
        try:
            args["aggregation"] = json.loads(aggregation_json)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse aggregation_json: {e}")
            # Do not add to args if invalid, or raise generic error?
            # Logging is safe fallback.
            pass

    return await call_mcp_tool_with_retry(
        create_monitoring_mcp_toolset,
        "list_timeseries",
        args,
        tool_context,
        project_id=project_id,
    )


@adk_tool
async def mcp_query_range(
    query: str,
    project_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    minutes_ago: int = 60,
    step: str = "60s",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Evaluate a PromQL query over a time range via Cloud Monitoring MCP.

    Use this for complex metric aggregations, calculations, and analysis using
    PromQL syntax. Ideal for rate calculations, histogram analysis, and
    multi-metric correlations.

    Args:
        query: PromQL query expression.
        project_id: GCP project ID. If not provided, uses default credentials.
        start_time: Start of query range (ISO format or RFC3339).
        end_time: End of query range (ISO format or RFC3339).
        minutes_ago: Minutes back from now for start time (default 60).
        step: Query resolution step (default "60s").
        tool_context: ADK tool context (required).

    Returns:
        Query results with time series data.

    Example queries:
        - 'rate(http_requests_total[5m])' - Request rate over 5 minutes
        - 'sum by (status_code)(http_requests_total)' - Requests grouped by status
        - 'histogram_quantile(0.95, http_request_duration_bucket)' - P95 latency
        - 'increase(errors_total[1h])' - Error count increase over 1 hour
    """
    if tool_context is None:
        raise ValueError("tool_context is required for MCP tools")

    import time as time_module

    # Build time range
    if end_time:
        end_str = end_time
    else:
        end_str = datetime.now(timezone.utc).isoformat()

    if start_time:
        start_str = start_time
    else:
        start_ts = time_module.time() - (minutes_ago * 60)
        start_str = datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat()

    args = {
        "query": query,
        "start": start_str,
        "end": end_str,
        "step": step,
    }

    return await call_mcp_tool_with_retry(
        create_monitoring_mcp_toolset,
        "query_range",
        args,
        tool_context,
        project_id=project_id,
    )
