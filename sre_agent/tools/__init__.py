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

Cross-Signal Correlation Tools (tools.correlation):
    - Trace-metrics correlation using exemplars
    - Trace-logs correlation using trace context
    - Cross-signal timeline alignment
    - Signal correlation strength analysis

Critical Path Analysis Tools (tools.correlation.critical_path):
    - Critical path identification in distributed traces
    - Bottleneck service detection
    - Parallelization opportunity analysis
    - Optimization recommendations

Service Dependency Tools (tools.correlation.dependencies):
    - Service dependency graph construction
    - Upstream/downstream impact analysis
    - Circular dependency detection
    - Hidden dependency discovery

SLO/SLI Tools (tools.clients.slo):
    - SLO listing and status
    - Error budget burn rate analysis
    - Golden signals (latency, traffic, errors, saturation)
    - SLO violation prediction
    - Incident-SLO impact correlation

GKE/Kubernetes Tools (tools.clients.gke):
    - Cluster health monitoring
    - Node pressure detection
    - Pod restart analysis
    - HPA scaling event tracking
    - OOM event detection
    - Trace-to-Kubernetes correlation

Remediation Tools (tools.analysis.remediation):
    - Automated remediation suggestions
    - gcloud command generation
    - Risk assessment
    - Similar incident lookup

Common Utilities (tools.common):
    - @adk_tool decorator with OpenTelemetry instrumentation
    - Telemetry helpers (tracer, meter)
    - Thread-safe caching for API responses
"""

# Common utilities
# BigQuery Analysis
from .analysis.bigquery.otel import (
    analyze_aggregate_metrics,
    compare_time_periods,
    correlate_logs_with_trace,
    detect_trend_changes,
    find_exemplar_traces,
)

# Critical Path Analysis
from .analysis.correlation.critical_path import (
    analyze_critical_path,
    calculate_critical_path_contribution,
    find_bottleneck_services,
)

# Cross-Signal Correlation
from .analysis.correlation.cross_signal import (
    analyze_signal_correlation_strength,
    build_cross_signal_timeline,
    correlate_metrics_with_traces_via_exemplars,
    correlate_trace_with_metrics,
)

# Service Dependency Analysis
from .analysis.correlation.dependencies import (
    analyze_upstream_downstream_impact,
    build_service_dependency_graph,
    detect_circular_dependencies,
    find_hidden_dependencies,
)

# Log Analysis
from .analysis.logs.extraction import (
    LogMessageExtractor,
    extract_log_message,
    extract_messages_from_entries,
)
from .analysis.logs.patterns import (
    LogPatternExtractor,
    analyze_log_anomalies,
    compare_log_patterns,
    extract_log_patterns,
    get_pattern_summary,
)

# Metrics Analysis
from .analysis.metrics import (
    calculate_series_stats,
    compare_metric_windows,
    detect_metric_anomalies,
)

# Trace Analysis
from .analysis.trace.analysis import (
    build_call_graph,
    calculate_span_durations,
    extract_errors,
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

# GCP tools
# GCP Clients
from .clients.logging import (
    get_logs_for_trace,
    list_error_events,
    list_log_entries,
)
from .clients.monitoring import (
    list_time_series,
    query_promql,
)

# SLO/SLI Tools
from .clients.slo import (
    analyze_error_budget_burn,
    correlate_incident_with_slo_impact,
    get_golden_signals,
    get_slo_status,
    list_slos,
    predict_slo_violation,
)

# GKE/Kubernetes Tools
from .clients.gke import (
    analyze_hpa_events,
    analyze_node_conditions,
    correlate_trace_with_kubernetes,
    get_container_oom_events,
    get_gke_cluster_health,
    get_pod_restart_events,
    get_workload_health_summary,
)

# Remediation Tools
from .analysis.remediation.suggestions import (
    estimate_remediation_risk,
    find_similar_past_incidents,
    generate_remediation_suggestions,
    get_gcloud_commands,
)

from .clients.trace import (
    fetch_trace,
    fetch_trace_data,
    find_example_traces,
    get_current_time,
    get_trace_by_url,
    list_traces,
    validate_trace,
)
from .common import (
    DataCache,
    adk_tool,
    get_data_cache,
    get_meter,
    get_tracer,
    log_tool_call,
)

# MCP Tools
from .mcp.gcp import (
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
    "DataCache",
    "LogMessageExtractor",
    # Log Analysis
    "LogPatternExtractor",
    # Trace Filters
    "TraceQueryBuilder",
    "TraceSelector",
    # Common
    "adk_tool",
    # BigQuery
    "analyze_aggregate_metrics",
    # Critical Path Analysis
    "analyze_critical_path",
    # SLO Analysis
    "analyze_error_budget_burn",
    # GKE Analysis
    "analyze_hpa_events",
    "analyze_log_anomalies",
    "analyze_node_conditions",
    "analyze_signal_correlation_strength",
    "analyze_upstream_downstream_impact",
    "build_call_graph",
    "build_cross_signal_timeline",
    # Service Dependency Analysis
    "build_service_dependency_graph",
    "build_trace_filter",
    "calculate_critical_path_contribution",
    "calculate_series_stats",
    # Trace Analysis
    "calculate_span_durations",
    "call_mcp_tool_with_retry",
    "compare_log_patterns",
    "compare_metric_windows",
    # Trace Comparison
    "compare_span_timings",
    "compare_time_periods",
    # Statistical Analysis
    "compute_latency_statistics",
    # SLO Correlation
    "correlate_incident_with_slo_impact",
    "correlate_logs_with_trace",
    "correlate_metrics_with_traces_via_exemplars",
    # Cross-Signal Correlation
    "correlate_trace_with_kubernetes",
    "correlate_trace_with_metrics",
    # GCP MCP
    "create_bigquery_mcp_toolset",
    "create_logging_mcp_toolset",
    "create_monitoring_mcp_toolset",
    "detect_circular_dependencies",
    "detect_latency_anomalies",
    # Metrics Analysis
    "detect_metric_anomalies",
    "detect_trend_changes",
    # Remediation
    "estimate_remediation_risk",
    "extract_errors",
    "extract_log_message",
    "extract_log_patterns",
    "extract_messages_from_entries",
    # Trace API
    "fetch_trace",
    "fetch_trace_data",
    "find_bottleneck_services",
    "find_example_traces",
    "find_exemplar_traces",
    "find_hidden_dependencies",
    "find_similar_past_incidents",
    "find_structural_differences",
    # Remediation
    "generate_remediation_suggestions",
    # GKE
    "get_container_oom_events",
    "get_current_time",
    "get_data_cache",
    "get_gcloud_commands",
    "get_gke_cluster_health",
    # SLO Golden Signals
    "get_golden_signals",
    "get_logs_for_trace",
    "get_meter",
    "get_pattern_summary",
    "get_pod_restart_events",
    "get_project_id_with_fallback",
    "get_slo_status",
    "get_trace_by_url",
    "get_tracer",
    "get_workload_health_summary",
    "list_error_events",
    # GCP Direct API
    "list_log_entries",
    # SLO
    "list_slos",
    "list_time_series",
    "list_traces",
    "log_tool_call",
    "mcp_list_log_entries",
    "mcp_list_timeseries",
    "mcp_query_range",
    # SLO Prediction
    "predict_slo_violation",
    "query_promql",
    "select_traces_from_error_reports",
    "select_traces_from_monitoring_alerts",
    "select_traces_from_statistical_outliers",
    "select_traces_manually",
    "summarize_trace",
    "validate_trace",
    "validate_trace_quality",
]
