"""SRE Agent Tools - Modular tooling for Google Cloud Observability.

This module provides a comprehensive set of tools for SRE tasks:

GCP Tools (tools.gcp):
    - BigQuery MCP for SQL-based data analysis
    - Cloud Logging MCP and direct API for log queries
    - Cloud Monitoring MCP and direct API for metrics
    - Error Reporting for error analysis

BigQuery Tools (tools.bigquery):
    - OpenTelemetry schema analysis tools
    - Aggregate metrics analysis
    - Exemplar trace selection
    - Time period comparison
    - Trend detection
    - Log correlation

Trace Tools (tools.trace):
    - Cloud Trace API clients for fetching traces
    - Trace analysis utilities (durations, errors, call graphs)
    - Trace comparison tools for diff analysis
    - Trace filter utilities

Common Utilities (tools.common):
    - @adk_tool decorator with OpenTelemetry instrumentation
    - Telemetry helpers (tracer, meter)
    - Thread-safe caching for API responses

Usage:
    from sre_agent.tools import fetch_trace, list_traces
    from sre_agent.tools.gcp import mcp_list_log_entries
    from sre_agent.tools.trace import compare_span_timings
    from sre_agent.tools.bigquery import analyze_aggregate_metrics
"""

# Common utilities
from .common import (
    adk_tool,
    get_tracer,
    get_meter,
    log_tool_call,
    DataCache,
    get_data_cache,
)

# GCP tools
from .gcp import (
    # MCP toolset factories
    create_bigquery_mcp_toolset,
    create_logging_mcp_toolset,
    create_monitoring_mcp_toolset,
    call_mcp_tool_with_retry,
    get_project_id_with_fallback,
    # MCP tools
    mcp_list_log_entries,
    mcp_list_timeseries,
    mcp_query_range,
    # Direct API tools
    list_log_entries,
    list_time_series,
    list_error_events,
    get_logs_for_trace,
    get_current_time,
)

# Trace tools
from .trace import (
    # API clients
    fetch_trace,
    fetch_trace_data,
    list_traces,
    find_example_traces,
    get_trace_by_url,
    validate_trace,
    # Analysis
    calculate_span_durations,
    extract_errors,
    build_call_graph,
    summarize_trace,
    validate_trace_quality,
    # Comparison
    compare_span_timings,
    find_structural_differences,
    # Filters
    TraceQueryBuilder,
    TraceSelector,
    build_trace_filter,
    select_traces_from_error_reports,
    select_traces_from_monitoring_alerts,
    select_traces_from_statistical_outliers,
    select_traces_manually,
)

# BigQuery tools
from .bigquery import (
    analyze_aggregate_metrics,
    find_exemplar_traces,
    compare_time_periods,
    detect_trend_changes,
    correlate_logs_with_trace,
)

__all__ = [
    # Common
    "adk_tool",
    "get_tracer",
    "get_meter",
    "log_tool_call",
    "DataCache",
    "get_data_cache",
    # GCP MCP
    "create_bigquery_mcp_toolset",
    "create_logging_mcp_toolset",
    "create_monitoring_mcp_toolset",
    "call_mcp_tool_with_retry",
    "get_project_id_with_fallback",
    "mcp_list_log_entries",
    "mcp_list_timeseries",
    "mcp_query_range",
    # GCP Direct API
    "list_log_entries",
    "list_time_series",
    "list_error_events",
    "get_logs_for_trace",
    "get_current_time",
    # Trace API
    "fetch_trace",
    "fetch_trace_data",
    "list_traces",
    "find_example_traces",
    "get_trace_by_url",
    "validate_trace",
    # Trace Analysis
    "calculate_span_durations",
    "extract_errors",
    "build_call_graph",
    "summarize_trace",
    "validate_trace_quality",
    # Trace Comparison
    "compare_span_timings",
    "find_structural_differences",
    # Trace Filters
    "TraceQueryBuilder",
    "TraceSelector",
    "build_trace_filter",
    "select_traces_from_error_reports",
    "select_traces_from_monitoring_alerts",
    "select_traces_from_statistical_outliers",
    "select_traces_manually",
    # BigQuery
    "analyze_aggregate_metrics",
    "find_exemplar_traces",
    "compare_time_periods",
    "detect_trend_changes",
    "correlate_logs_with_trace",
]
