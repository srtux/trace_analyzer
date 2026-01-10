"""Google Cloud Platform tools for SRE Agent.

This module provides tools for interacting with GCP Observability services:
- BigQuery MCP for SQL-based analysis
- Cloud Logging MCP for log queries
- Cloud Monitoring MCP for metrics queries
- Direct API clients as fallback

MCP Tools (via Model Context Protocol):
- BigQuery: execute_sql, list_dataset_ids, list_table_ids, get_table_info
- Logging: list_log_entries
- Monitoring: list_timeseries, query_range

Direct API Tools:
- Logging: list_log_entries, get_logs_for_trace
- Monitoring: list_time_series
- Error Reporting: list_error_events
"""

from ..clients.logging import (
    get_logs_for_trace,
    list_error_events,
    list_log_entries,
)
from ..clients.monitoring import list_time_series
from ..clients.trace import get_current_time
from .gcp import (
    call_mcp_tool_with_retry,
    create_bigquery_mcp_toolset,
    create_logging_mcp_toolset,
    create_monitoring_mcp_toolset,
    get_project_id_with_fallback,
    mcp_list_log_entries,
    mcp_list_timeseries,
    mcp_query_range,
)

__all__ = [
    "call_mcp_tool_with_retry",
    # MCP toolset factories
    "create_bigquery_mcp_toolset",
    "create_logging_mcp_toolset",
    "create_monitoring_mcp_toolset",
    "get_current_time",
    "get_logs_for_trace",
    # Utilities
    "get_project_id_with_fallback",
    "list_error_events",
    # Direct API tools
    "list_log_entries",
    "list_time_series",
    # MCP tools
    "mcp_list_log_entries",
    "mcp_list_timeseries",
    "mcp_query_range",
]
