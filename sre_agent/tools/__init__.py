"""SRE Agent Tools - Modular tooling for Google Cloud Observability.

This module provides a comprehensive set of tools for SRE tasks:

MCP Tools for GCP (tools.mcp.gcp):
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
    - Statistical analysis tools

Log Analysis Tools (tools.logs):
    - Log pattern extraction using Drain3 algorithm
    - Pattern comparison between time periods
    - Anomaly detection for emergent log patterns
    - Smart payload extraction from various formats

Common Utilities (tools.common):
    - @adk_tool decorator with OpenTelemetry instrumentation
    - Telemetry helpers (tracer, meter)
    - Thread-safe caching for API responses
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
# GCP Clients
from .clients.logging import (
    list_log_entries,
    list_error_events,
    get_logs_for_trace,
)
from .clients.monitoring import (
    list_time_series,
    query_promql,
)
from .clients.trace import (
    fetch_trace,
    fetch_trace_data,
    list_traces,
    find_example_traces,
    get_trace_by_url,
    validate_trace,
    get_current_time,
)

# MCP Tools
from .mcp.gcp import (
    get_project_id_with_fallback,
    create_logging_mcp_toolset,
    mcp_list_log_entries,
    create_monitoring_mcp_toolset,
    mcp_list_timeseries,
    mcp_query_range,
    create_bigquery_mcp_toolset,
    call_mcp_tool_with_retry,
)

# Trace Analysis
from .analysis.trace.analysis import (
    calculate_span_durations,
    extract_errors,
    build_call_graph,
    summarize_trace,
    validate_trace_quality,
)
from .analysis.trace.comparison import (
    compare_span_timings,
    find_structural_differences,
)
from .analysis.trace.filters import (
    TraceQueryBuilder,
    TraceSelector,
    build_trace_filter,
    select_traces_from_error_reports,
    select_traces_from_monitoring_alerts,
    select_traces_from_statistical_outliers,
    select_traces_manually,
)
from .analysis.trace.statistical_analysis import (
    compute_latency_statistics,
    detect_latency_anomalies,
)

# BigQuery Analysis
from .analysis.bigquery.otel import (
    analyze_aggregate_metrics,
    find_exemplar_traces,
    compare_time_periods,
    detect_trend_changes,
    correlate_logs_with_trace,
)

# Metrics Analysis
from .analysis.metrics import (
    detect_metric_anomalies,
    compare_metric_windows,
    calculate_series_stats,
)

# Log Analysis
from .analysis.logs.extraction import (
    extract_log_message,
    extract_messages_from_entries,
    LogMessageExtractor,
)
from .analysis.logs.patterns import (
    LogPatternExtractor,
    extract_log_patterns,
    compare_log_patterns,
    analyze_log_anomalies,
    get_pattern_summary,
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
    "query_promql",
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
    # Statistical Analysis
    "compute_latency_statistics",
    "detect_latency_anomalies",
    # BigQuery
    "analyze_aggregate_metrics",
    "find_exemplar_traces",
    "compare_time_periods",
    "detect_trend_changes",
    "correlate_logs_with_trace",
    # Log Analysis
    "LogPatternExtractor",
    "extract_log_patterns",
    "compare_log_patterns",
    "analyze_log_anomalies",
    "get_pattern_summary",
    "extract_log_message",
    "extract_messages_from_entries",
    "LogMessageExtractor",
    # Metrics Analysis
    "detect_metric_anomalies",
    "compare_metric_windows",
    "calculate_series_stats",
]
