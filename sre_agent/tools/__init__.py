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
    select_traces_from_statistical_outliers,
    select_traces_manually,
)

# Analysis Tools - Trace
from .analysis.trace.statistical_analysis import (
    analyze_trace_patterns,
    compute_latency_statistics,
    detect_latency_anomalies,
    perform_causal_analysis,
)
from .clients.alerts import get_alert, list_alert_policies, list_alerts
from .clients.gcp_projects import list_gcp_projects
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

# Configuration
from .config import (
    ToolCategory,
    ToolConfig,
    ToolConfigManager,
    ToolTestResult,
    ToolTestStatus,
    get_tool_config_manager,
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
    mcp_execute_sql,
    mcp_list_log_entries,
    mcp_list_timeseries,
    mcp_query_range,
)

# Reporting Tools
from .reporting import synthesize_report

__all__ = [
    "analyze_aggregate_metrics",
    "analyze_bigquery_log_patterns",
    "analyze_critical_path",
    "analyze_error_budget_burn",
    "analyze_hpa_events",
    "analyze_log_anomalies",
    "analyze_node_conditions",
    "analyze_signal_correlation_strength",
    "analyze_trace_patterns",
    "analyze_upstream_downstream_impact",
    "build_call_graph",
    "build_cross_signal_timeline",
    "build_service_dependency_graph",
    "calculate_critical_path_contribution",
    "calculate_series_stats",
    "calculate_span_durations",
    "call_mcp_tool_with_retry",
    "compare_log_patterns",
    "compare_metric_windows",
    "compare_span_timings",
    "compare_time_periods",
    "compute_latency_statistics",
    "correlate_incident_with_slo_impact",
    "correlate_logs_with_trace",
    "correlate_metrics_with_traces_via_exemplars",
    "correlate_trace_with_kubernetes",
    "correlate_trace_with_metrics",
    "create_bigquery_mcp_toolset",
    "create_logging_mcp_toolset",
    "create_monitoring_mcp_toolset",
    "detect_circular_dependencies",
    "detect_latency_anomalies",
    "detect_metric_anomalies",
    "detect_trend_changes",
    "discover_telemetry_sources",
    "estimate_remediation_risk",
    "extract_errors",
    "extract_log_patterns",
    "fetch_trace",
    "find_bottleneck_services",
    "find_example_traces",
    "find_exemplar_traces",
    "find_hidden_dependencies",
    "find_similar_past_incidents",
    "find_structural_differences",
    "generate_remediation_suggestions",
    "get_alert",
    "get_container_oom_events",
    "get_current_time",
    "get_gcloud_commands",
    "get_gke_cluster_health",
    "get_golden_signals",
    "get_logs_for_trace",
    "get_pod_restart_events",
    "get_project_id_with_fallback",
    "get_slo_status",
    "get_trace_by_url",
    "get_workload_health_summary",
    "list_alert_policies",
    "list_alerts",
    "list_error_events",
    "list_gcp_projects",
    "list_log_entries",
    "list_slos",
    "list_time_series",
    "list_traces",
    "mcp_list_log_entries",
    "mcp_list_timeseries",
    "mcp_query_range",
    "mcp_execute_sql",
    "perform_causal_analysis",
    "predict_slo_violation",
    "query_promql",
    "select_traces_from_statistical_outliers",
    "select_traces_manually",
    "summarize_trace",
    "synthesize_report",
    "validate_trace_quality",
    # Configuration
    "ToolCategory",
    "ToolConfig",
    "ToolConfigManager",
    "ToolTestResult",
    "ToolTestStatus",
    "get_tool_config_manager",
]
