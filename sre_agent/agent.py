"""SRE Agent - Google Cloud Observability Analysis Agent.

This is the main agent for SRE tasks, specializing in analyzing telemetry data
from Google Cloud Observability: traces, logs, and metrics.

Capabilities:

Trace Analysis (Multi-Stage Pipeline):
- Stage 0 (Aggregate): BigQuery-powered analysis of thousands of traces
- Stage 1 (Triage): Parallel analysis with 4 specialized sub-agents
- Stage 2 (Deep Dive): Root cause and impact analysis

Log Analysis:
- Pattern extraction using Drain3 algorithm
- Time period comparison for anomaly detection
- Smart message extraction from various payload formats

Metrics Analysis:
- Direct API and MCP tools for Cloud Monitoring
- PromQL queries for complex aggregations
"""

import asyncio
import logging
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool, ToolContext

from .prompt import SRE_AGENT_PROMPT

# Import sub-agents
from .sub_agents import (
    # Trace analysis sub-agents
    aggregate_analyzer,
    causality_analyzer,
    error_analyzer,
    latency_analyzer,
    # Log analysis sub-agents
    log_pattern_extractor,
    # Metrics analysis sub-agents
    metrics_analyzer,
    service_impact_analyzer,
    statistics_analyzer,
    structure_analyzer,
)
from .tools import (
    # BigQuery tools
    analyze_aggregate_metrics,
    # Critical path analysis tools
    analyze_critical_path,
    # SLO/SLI tools
    analyze_error_budget_burn,
    # GKE tools
    analyze_hpa_events,
    analyze_log_anomalies,
    analyze_node_conditions,
    analyze_signal_correlation_strength,
    analyze_upstream_downstream_impact,
    build_call_graph,
    build_cross_signal_timeline,
    # Service dependency tools
    build_service_dependency_graph,
    calculate_critical_path_contribution,
    calculate_series_stats,
    calculate_span_durations,
    compare_log_patterns,
    compare_metric_windows,
    compare_span_timings,
    compare_time_periods,
    # SLO correlation
    correlate_incident_with_slo_impact,
    correlate_logs_with_trace,
    correlate_metrics_with_traces_via_exemplars,
    # Cross-signal correlation tools
    correlate_trace_with_kubernetes,
    correlate_trace_with_metrics,
    detect_circular_dependencies,
    # Metrics analysis tools
    detect_metric_anomalies,
    detect_trend_changes,
    # Remediation tools
    estimate_remediation_risk,
    extract_errors,
    # Log pattern analysis tools
    extract_log_patterns,
    # Trace tools
    fetch_trace,
    find_bottleneck_services,
    find_example_traces,
    find_exemplar_traces,
    find_hidden_dependencies,
    find_similar_past_incidents,
    find_structural_differences,
    # Remediation
    generate_remediation_suggestions,
    # GKE tools
    get_container_oom_events,
    get_current_time,
    get_gcloud_commands,
    get_gke_cluster_health,
    # SLO Golden Signals
    get_golden_signals,
    get_logs_for_trace,
    get_pod_restart_events,
    get_slo_status,
    get_trace_by_url,
    get_workload_health_summary,
    list_error_events,
    # GCP direct API tools
    list_log_entries,
    # SLO listing
    list_slos,
    list_time_series,
    list_traces,
    # SLO prediction
    predict_slo_violation,
    query_promql,
    # Trace selection tools
    select_traces_from_error_reports,
    select_traces_from_monitoring_alerts,
    select_traces_from_statistical_outliers,
    select_traces_manually,
    summarize_trace,
    validate_trace_quality,
)
from .tools.common import adk_tool
from .tools.mcp.gcp import (
    create_bigquery_mcp_toolset,
    create_logging_mcp_toolset,
    create_monitoring_mcp_toolset,
    get_project_id_with_fallback,
    mcp_list_log_entries,
    mcp_list_timeseries,
    mcp_query_range,
)

logger = logging.getLogger(__name__)

# ============================================================================
# MCP Toolset Management
# ============================================================================

# Lazy-loaded MCP toolsets (created on first use in async context)
_bigquery_mcp_toolset = None
_logging_mcp_toolset = None
_monitoring_mcp_toolset = None


async def _get_bigquery_mcp_toolset():
    """Lazily create BigQuery MCP toolset in async context."""
    global _bigquery_mcp_toolset
    if _bigquery_mcp_toolset is None:
        _bigquery_mcp_toolset = create_bigquery_mcp_toolset()
    return _bigquery_mcp_toolset


async def _get_logging_mcp_toolset():
    """Lazily create Cloud Logging MCP toolset in async context."""
    global _logging_mcp_toolset
    if _logging_mcp_toolset is None:
        _logging_mcp_toolset = create_logging_mcp_toolset()
    return _logging_mcp_toolset


async def _get_monitoring_mcp_toolset():
    """Lazily create Cloud Monitoring MCP toolset in async context."""
    global _monitoring_mcp_toolset
    if _monitoring_mcp_toolset is None:
        _monitoring_mcp_toolset = create_monitoring_mcp_toolset()
    return _monitoring_mcp_toolset


# ============================================================================
# Orchestration Functions
# ============================================================================


@adk_tool
async def run_aggregate_analysis(
    dataset_id: str,
    table_name: str,
    time_window_hours: int = 24,
    service_name: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """
    Run Stage 0: Aggregate analysis using BigQuery.

    This stage analyzes thousands of traces to identify patterns, trends,
    and select exemplar traces for detailed investigation.

    Args:
        dataset_id: BigQuery dataset ID (e.g., 'project.dataset')
        table_name: Table name containing OTel traces
        time_window_hours: Time window for analysis
        service_name: Optional service filter
        tool_context: ADK tool context

    Returns:
        Aggregate analysis results with recommended traces.
    """
    logger.info(f"Running aggregate analysis on {dataset_id}.{table_name}")

    if tool_context is None:
        raise ValueError("tool_context is required")

    try:
        # Run aggregate analyzer sub-agent
        result = await AgentTool(aggregate_analyzer).run_async(
            args={
                "request": f"""
Analyze trace data in BigQuery:
- Dataset: {dataset_id}
- Table: {table_name}
- Time window: {time_window_hours} hours
{f"- Service filter: {service_name}" if service_name else ""}

Please:
1. Get aggregate metrics for all services
2. Identify services with high error rates or latency
3. Find exemplar traces for comparison (baseline and outlier)
4. Report your findings
""",
            },
            tool_context=tool_context,
        )

        return {
            "stage": "aggregate",
            "status": "success",
            "result": result,
        }

    except Exception as e:
        logger.error(f"Aggregate analysis failed: {e}", exc_info=True)
        return {
            "stage": "aggregate",
            "status": "error",
            "error": str(e),
        }


@adk_tool
async def run_triage_analysis(
    baseline_trace_id: str,
    target_trace_id: str,
    project_id: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """
    Run Stage 1: Parallel triage analysis with 4 specialized sub-agents.

    This stage compares two traces in parallel using:
    - Latency Analyzer: Timing comparison
    - Error Analyzer: Error detection
    - Structure Analyzer: Call graph comparison
    - Statistics Analyzer: Statistical anomaly detection

    Args:
        baseline_trace_id: ID of the reference (good) trace
        target_trace_id: ID of the trace to investigate
        project_id: GCP project ID (optional, uses env if not provided)
        tool_context: ADK tool context

    Returns:
        Combined results from all triage analyzers.
    """
    if tool_context is None:
        raise ValueError("tool_context is required")

    if not project_id:
        project_id = get_project_id_with_fallback()

    logger.info(f"Running triage analysis: {baseline_trace_id} vs {target_trace_id}")

    prompt = f"""
Analyze the differences between these two traces:
- Baseline (good): {baseline_trace_id}
- Target (investigate): {target_trace_id}
- Project: {project_id}

Compare them and report your findings.
"""

    # Run all triage analyzers in parallel
    results = await asyncio.gather(
        AgentTool(latency_analyzer).run_async(
            args={"request": prompt}, tool_context=tool_context
        ),
        AgentTool(error_analyzer).run_async(
            args={"request": prompt}, tool_context=tool_context
        ),
        AgentTool(structure_analyzer).run_async(
            args={"request": prompt}, tool_context=tool_context
        ),
        AgentTool(statistics_analyzer).run_async(
            args={"request": prompt}, tool_context=tool_context
        ),
        return_exceptions=True,
    )

    agent_names = ["latency", "error", "structure", "statistics"]
    triage_results: dict[str, dict[str, Any]] = {}

    for name, result in zip(agent_names, results, strict=False):
        if isinstance(result, Exception):
            logger.error(f"{name}_analyzer failed: {result}")
            triage_results[name] = {"status": "error", "error": str(result)}
        else:
            triage_results[name] = {"status": "success", "result": result}  # type: ignore

    return {
        "stage": "triage",
        "baseline_trace_id": baseline_trace_id,
        "target_trace_id": target_trace_id,
        "results": triage_results,
    }


@adk_tool
async def run_log_pattern_analysis(
    log_filter: str,
    baseline_start: str,
    baseline_end: str,
    comparison_start: str,
    comparison_end: str,
    project_id: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """
    Run log pattern analysis to find emergent issues.

    This function compares log patterns between two time periods using
    the Drain3 algorithm to identify NEW patterns that may indicate issues.

    Args:
        log_filter: Cloud Logging filter (e.g., 'resource.type="k8s_container"')
        baseline_start: Start of baseline period (RFC3339)
        baseline_end: End of baseline period (RFC3339)
        comparison_start: Start of comparison period (RFC3339)
        comparison_end: End of comparison period (RFC3339)
        project_id: GCP project ID
        tool_context: ADK tool context

    Returns:
        Pattern comparison results with anomalies.
    """
    if not project_id:
        project_id = get_project_id_with_fallback()

    logger.info(f"Running log pattern analysis for filter: {log_filter}")

    if tool_context is None:
        raise ValueError("tool_context is required")

    try:
        result = await AgentTool(log_pattern_extractor).run_async(
            args={
                "request": f"""
Analyze log patterns and find anomalies:

Filter: {log_filter}
Project: {project_id}

Baseline Period (before):
- Start: {baseline_start}
- End: {baseline_end}

Comparison Period (during/after):
- Start: {comparison_start}
- End: {comparison_end}

Please:
1. Fetch logs from both periods using the filter
2. Extract patterns from each period using extract_log_patterns
3. Compare the patterns to find NEW or INCREASED patterns
4. Focus on ERROR patterns as they are most likely to indicate issues
5. Report your findings with recommendations
""",
            },
            tool_context=tool_context,
        )

        return {
            "stage": "log_pattern_analysis",
            "status": "success",
            "result": result,
        }

    except Exception as e:
        logger.error(f"Log pattern analysis failed: {e}", exc_info=True)
        return {
            "stage": "log_pattern_analysis",
            "status": "error",
            "error": str(e),
        }


@adk_tool
async def run_deep_dive_analysis(
    baseline_trace_id: str,
    target_trace_id: str,
    triage_findings: dict[str, Any],
    project_id: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """
    Run Stage 2: Deep dive analysis with causality and impact sub-agents.

    This stage determines:
    - Causality: What is the root cause of the issue?
    - Service Impact: What is the blast radius?

    Args:
        baseline_trace_id: ID of the baseline trace
        target_trace_id: ID of the target trace
        triage_findings: Results from Stage 1 triage
        project_id: GCP project ID
        tool_context: ADK tool context

    Returns:
        Root cause analysis and service impact assessment.
    """
    if tool_context is None:
        raise ValueError("tool_context is required")

    if not project_id:
        project_id = get_project_id_with_fallback()

    logger.info(f"Running deep dive analysis for trace {target_trace_id}")

    prompt = f"""
Based on the triage findings, perform deep analysis:

Traces:
- Baseline: {baseline_trace_id}
- Target: {target_trace_id}
- Project: {project_id}

Triage Summary:
{triage_findings}

Determine root cause and assess impact.
"""

    # Run deep dive analyzers in parallel
    results = await asyncio.gather(
        AgentTool(causality_analyzer).run_async(
            args={"request": prompt}, tool_context=tool_context
        ),
        AgentTool(service_impact_analyzer).run_async(
            args={"request": prompt}, tool_context=tool_context
        ),
        return_exceptions=True,
    )

    agent_names = ["causality", "service_impact"]
    deep_dive_results: dict[str, dict[str, Any]] = {}

    for name, result in zip(agent_names, results, strict=False):
        if isinstance(result, Exception):
            logger.error(f"{name}_analyzer failed: {result}")
            deep_dive_results[name] = {"status": "error", "error": str(result)}
        else:
            deep_dive_results[name] = {"status": "success", "result": result}  # type: ignore

    return {
        "stage": "deep_dive",
        "results": deep_dive_results,
    }


# ============================================================================
# ============================================================================
# Base Tools (always available)
# ============================================================================

base_tools = [
    # Trace API tools
    fetch_trace,
    list_traces,
    find_example_traces,
    get_trace_by_url,
    # Trace analysis tools
    calculate_span_durations,
    extract_errors,
    build_call_graph,
    summarize_trace,
    validate_trace_quality,
    # Trace comparison tools
    compare_span_timings,
    find_structural_differences,
    # GCP direct API tools
    list_log_entries,
    list_time_series,
    query_promql,
    list_error_events,
    get_logs_for_trace,
    get_current_time,
    # BigQuery OTel tools
    analyze_aggregate_metrics,
    find_exemplar_traces,
    compare_time_periods,
    detect_trend_changes,
    correlate_logs_with_trace,
    # Log pattern analysis tools (Drain3)
    extract_log_patterns,
    compare_log_patterns,
    analyze_log_anomalies,
    # MCP tools (wrapper functions)
    mcp_list_log_entries,
    mcp_list_timeseries,
    mcp_query_range,
    # Orchestrator tools
    run_aggregate_analysis,
    run_triage_analysis,
    run_log_pattern_analysis,
    run_deep_dive_analysis,
    # Trace Selection tools
    select_traces_from_error_reports,
    select_traces_from_monitoring_alerts,
    select_traces_from_statistical_outliers,
    select_traces_manually,
    # Metrics analysis tools
    detect_metric_anomalies,
    compare_metric_windows,
    calculate_series_stats,
    # Cross-signal correlation tools
    correlate_trace_with_metrics,
    correlate_metrics_with_traces_via_exemplars,
    build_cross_signal_timeline,
    analyze_signal_correlation_strength,
    # Critical path analysis tools
    analyze_critical_path,
    find_bottleneck_services,
    calculate_critical_path_contribution,
    # Service dependency tools
    build_service_dependency_graph,
    analyze_upstream_downstream_impact,
    detect_circular_dependencies,
    find_hidden_dependencies,
    # =================================================================
    # NEW: SLO/SLI Tools - The SRE Golden Signals Framework
    # =================================================================
    list_slos,
    get_slo_status,
    analyze_error_budget_burn,
    get_golden_signals,
    correlate_incident_with_slo_impact,
    predict_slo_violation,
    # =================================================================
    # NEW: GKE/Kubernetes Tools - Container Orchestration Debugging
    # =================================================================
    get_gke_cluster_health,
    analyze_node_conditions,
    get_pod_restart_events,
    analyze_hpa_events,
    get_container_oom_events,
    correlate_trace_with_kubernetes,
    get_workload_health_summary,
    # =================================================================
    # NEW: Automated Remediation Tools - From Diagnosis to Treatment
    # =================================================================
    generate_remediation_suggestions,
    get_gcloud_commands,
    estimate_remediation_risk,
    find_similar_past_incidents,
]


# ============================================================================
# Main Agent Definition
# ============================================================================

# Create the main SRE Agent
sre_agent = LlmAgent(
    name="sre_agent",
    model="gemini-2.5-pro",
    description=(
        "The world's most comprehensive SRE Agent for Google Cloud. "
        "Analyzes traces, logs, and metrics with cross-signal correlation via exemplars. "
        "Features: SLO/SLI framework with error budget tracking, GKE/Kubernetes debugging, "
        "critical path analysis, service dependency mapping, and automated remediation suggestions. "
        "Supports Cloud Trace, Cloud Logging, Cloud Monitoring, BigQuery, GKE, and Cloud Run."
    ),
    instruction=SRE_AGENT_PROMPT,
    tools=base_tools,  # type: ignore
    # Sub-agents for specialized analysis (automatically invoked based on task)
    sub_agents=[
        # Trace analysis sub-agents
        aggregate_analyzer,
        latency_analyzer,
        error_analyzer,
        structure_analyzer,
        statistics_analyzer,
        causality_analyzer,
        service_impact_analyzer,
        # Log analysis sub-agents
        log_pattern_extractor,
        # Metrics analysis sub-agents
        metrics_analyzer,
    ],
)

# Export as root_agent for ADK CLI compatibility
root_agent = sre_agent

# ============================================================================
# Dynamic Tool Loading
# ============================================================================


async def get_agent_with_mcp_tools():
    """
    Creates an agent instance with MCP toolsets loaded.

    This should be called in an async context to properly initialize
    MCP toolsets. Use this for programmatic agent creation.

    Returns:
        LlmAgent with MCP tools added.
    """
    # Get MCP toolsets
    bq_toolset = await _get_bigquery_mcp_toolset()
    logging_toolset = await _get_logging_mcp_toolset()
    monitoring_toolset = await _get_monitoring_mcp_toolset()

    # Combine all tools
    all_tools = list(base_tools)

    # Add MCP toolsets if available
    if bq_toolset:
        all_tools.append(bq_toolset)
    if logging_toolset:
        all_tools.append(logging_toolset)
    if monitoring_toolset:
        all_tools.append(monitoring_toolset)

    # Create agent with all tools
    return LlmAgent(
        name="sre_agent",
        model="gemini-2.5-pro",
        description=sre_agent.description,
        instruction=SRE_AGENT_PROMPT,
        tools=all_tools,
        sub_agents=[
            # Trace analysis sub-agents
            aggregate_analyzer,
            latency_analyzer,
            error_analyzer,
            structure_analyzer,
            statistics_analyzer,
            causality_analyzer,
            service_impact_analyzer,
            # Log analysis sub-agents
            log_pattern_extractor,
            # Metrics analysis sub-agents
            metrics_analyzer,
        ],
    )
