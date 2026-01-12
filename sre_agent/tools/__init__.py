"""Google Cloud Platform tools for SRE Agent.

This module provides tools for interacting with GCP Observability services:
- BigQuery MCP for SQL-based analysis
- Cloud Logging MCP for log queries
- Cloud Monitoring MCP for metrics queries
- Direct API clients as fallback
- Analysis tools for Traces, Logs, Metrics, GKE, SLOs, and Remediation
"""

# Client Tools
# Analysis Tools - BigQuery
from .analysis.bigquery.logs import analyze_bigquery_log_patterns
from .analysis.bigquery.otel import (
    analyze_aggregate_metrics,
    compare_time_periods,
    correlate_logs_with_trace,
    detect_trend_changes,
    find_exemplar_traces,
)

# Analysis Tools - Correlation
from .analysis.correlation.critical_path import (
    analyze_critical_path,
    calculate_critical_path_contribution,
    find_bottleneck_services,
)
from .analysis.correlation.cross_signal import (
    analyze_signal_correlation_strength,
    build_cross_signal_timeline,
    correlate_metrics_with_traces_via_exemplars,
    correlate_trace_with_metrics,
)
from .analysis.correlation.dependencies import (
    analyze_upstream_downstream_impact,
    build_service_dependency_graph,
    detect_circular_dependencies,
    find_hidden_dependencies,
)

# Analysis Tools - Logs
from .analysis.logs.patterns import (
    analyze_log_anomalies,
    compare_log_patterns,
    extract_log_patterns,
)

# Analysis Tools - Metrics
from .analysis.metrics.anomaly_detection import (
    compare_metric_windows,
    detect_metric_anomalies,
)
from .analysis.metrics.statistics import (
    calculate_series_stats,
)

# Analysis Tools - Remediation
from .analysis.remediation.suggestions import (
    estimate_remediation_risk,
    find_similar_past_incidents,
    generate_remediation_suggestions,
    get_gcloud_commands,
)

# Analysis Tools - Trace
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
    select_traces_from_error_reports,
    select_traces_from_monitoring_alerts,
    select_traces_from_statistical_outliers,
    select_traces_manually,
)
from .clients.gke import (
    analyze_hpa_events,
    analyze_node_conditions,
    correlate_trace_with_kubernetes,
    get_container_oom_events,
    get_gke_cluster_health,
    get_pod_restart_events,
    get_workload_health_summary,
)
from .clients.logging import (
    get_logs_for_trace,
    list_error_events,
    list_log_entries,
)
from .clients.monitoring import list_time_series, query_promql
from .clients.slo import (
    analyze_error_budget_burn,
    correlate_incident_with_slo_impact,
    get_golden_signals,
    get_slo_status,
    list_slos,
    predict_slo_violation,
)
from .clients.trace import (
    fetch_trace,
    find_example_traces,
    get_current_time,
    get_trace_by_url,
    list_traces,
)

# Discovery Tools
from .discovery.discovery_tool import discover_telemetry_sources

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

# Reporting Tools
from .reporting import synthesize_report

__all__ = [
    # Clients - Logging
    "get_logs_for_trace",
    "list_error_events",
    "list_log_entries",
    # Clients - Monitoring
    "list_time_series",
    "query_promql",
    # Clients - Trace
    "get_current_time",
    "fetch_trace",
    "list_traces",
    "get_trace_by_url",
    "find_example_traces",
    # Clients - GKE
    "get_gke_cluster_health",
    "get_workload_health_summary",
    "analyze_node_conditions",
    "get_pod_restart_events",
    "analyze_hpa_events",
    "get_container_oom_events",
    "correlate_trace_with_kubernetes",
    # Clients - SLO
    "list_slos",
    "get_slo_status",
    "analyze_error_budget_burn",
    "get_golden_signals",
    "correlate_incident_with_slo_impact",
    "predict_slo_violation",
    # Discovery
    "discover_telemetry_sources",
    # Reporting
    "synthesize_report",
    # Analysis - BigQuery
    "analyze_aggregate_metrics",
    "find_exemplar_traces",
    "correlate_logs_with_trace",
    "compare_time_periods",
    "detect_trend_changes",
    "analyze_bigquery_log_patterns",
    # Analysis - Trace
    "extract_errors",
    "build_call_graph",
    "calculate_span_durations",
    "compare_span_timings",
    "find_structural_differences",
    "summarize_trace",
    "validate_trace_quality",
    "select_traces_from_error_reports",
    "select_traces_from_monitoring_alerts",
    "select_traces_from_statistical_outliers",
    "select_traces_manually",
    # Analysis - Logs
    "analyze_log_anomalies",
    "extract_log_patterns",
    "compare_log_patterns",
    # Analysis - Metrics
    "detect_metric_anomalies",
    "compare_metric_windows",
    "calculate_series_stats",
    # Analysis - Correlation
    "analyze_critical_path",
    "find_bottleneck_services",
    "calculate_critical_path_contribution",
    "build_service_dependency_graph",
    "analyze_upstream_downstream_impact",
    "detect_circular_dependencies",
    "find_hidden_dependencies",
    "correlate_trace_with_metrics",
    "correlate_metrics_with_traces_via_exemplars",
    "build_cross_signal_timeline",
    "analyze_signal_correlation_strength",
    # Analysis - Remediation
    "generate_remediation_suggestions",
    "find_similar_past_incidents",
    "estimate_remediation_risk",
    "get_gcloud_commands",
    # MCP
    "call_mcp_tool_with_retry",
    "create_bigquery_mcp_toolset",
    "create_logging_mcp_toolset",
    "create_monitoring_mcp_toolset",
    "get_project_id_with_fallback",
    "mcp_list_log_entries",
    "mcp_list_timeseries",
    "mcp_query_range",
]
