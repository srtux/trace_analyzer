"""SRE Agent - Google Cloud Observability Analysis Agent.

This is the main orchestration agent for SRE tasks, designed to analyze telemetry data
from Google Cloud Observability (Traces, Logs, Metrics) to identify root causes of
production issues.

## Architecture: "Council of Experts"

The agent uses a "Council of Experts" orchestration pattern where a central
**SRE Agent** delegates specialized tasks to domain-specific sub-agents.

### The 3-Stage Analysis Pipeline

1.  **Stage 0: Aggregate Analysis (Data Analyst)**
    -   **Sub-Agent**: `aggregate_analyzer`
    -   **Goal**: Analyze thousands of traces in BigQuery to identify trends,
        patterns, and outlier services without manual inspection.
    -   **Output**: A list of "Exemplar Traces" (baselines and anomalies) to investigate.

2.  **Stage 1: Triage (The Squad)**
    -   **Goal**: Parallel inspection of specific traces to identify *what* is wrong.
    -   **Sub-Agents**:
        -   `latency_analyzer`: Finds critical path and bottlenecks.
        -   `error_analyzer`: Diagnoses specific error codes and failure points.
        -   `structure_analyzer`: Detects changes in call graph topology (e.g., new dependencies).
        -   `statistics_analyzer`: Calculates z-scores and statistical significance of anomalies.
        -   `resiliency_architect`: Detects anti-patterns like retry storms and cascading failures.

3.  **Stage 2: Deep Dive (Root Cause)**
    -   **Goal**: Synthesize findings to determine *why* it happened and *who* is impacted.
    -   **Sub-Agents**:
        -   `causality_analyzer`: Correlates traces, logs, and metrics to find the "smoking gun".
        -   `service_impact_analyzer`: Assesses the "blast radius" (upstream/downstream impact).
        -   `change_detective`: Correlates incidents with recent deployments or config changes.

## Capabilities

-   **Trace Analysis**: Full-spectrum analysis from aggregate BigQuery stats to individual span inspection.
-   **Log Analysis**: Pattern extraction (Drain3), anomaly detection, and correlation with traces.
-   **Metrics Analysis**: PromQL querying, anomaly detection, and cross-signal correlation.
-   **SLO/SLI Support**: Error budget tracking, burn rate analysis, and violation prediction.
-   **Kubernetes/GKE**: Cluster health, node pressure, and workload debugging.
-   **Automated Remediation**: Actionable suggestions and risk-assessed gcloud commands.

## Tooling Strategy

The agent employs a hybrid tooling strategy:
-   **MCP (Model Context Protocol)**: For heavy-lifting, stateful operations (BigQuery, complex queries).
-   **Direct API Clients**: For low-latency, stateless operations (Trace fetching, light logging).
-   **Analysis Engines**: Python-based logic for statistical analysis, graph traversal, and pattern matching.
"""

import asyncio
import functools
import logging
import os
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool, ToolContext  # type: ignore[attr-defined]
from google.adk.tools.base_toolset import BaseToolset

from .prompt import SRE_AGENT_PROMPT

# Import sub-agents
from .sub_agents import (
    # Trace analysis sub-agents
    aggregate_analyzer,
    # Alert analysis sub-agents
    alert_analyst,
    causality_analyzer,
    # New Sub-Agents
    change_detective,
    error_analyzer,
    latency_analyzer,
    # Log analysis sub-agents
    log_analyst,
    # Metrics analysis sub-agents
    metrics_analyzer,
    resiliency_architect,
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
    analyze_trace_patterns,
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
    compute_latency_statistics,
    # SLO correlation
    correlate_incident_with_slo_impact,
    correlate_logs_with_trace,
    correlate_metrics_with_traces_via_exemplars,
    # Cross-signal correlation tools
    correlate_trace_with_kubernetes,
    correlate_trace_with_metrics,
    detect_all_sre_patterns,
    detect_cascading_timeout,
    detect_circular_dependencies,
    detect_connection_pool_issues,
    detect_latency_anomalies,
    # Metrics analysis tools
    detect_metric_anomalies,
    detect_retry_storm,
    detect_trend_changes,
    # Discovery tools
    discover_telemetry_sources,
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
    get_alert,
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
    list_alert_policies,
    # Alerting tools
    list_alerts,
    list_error_events,
    # GCP direct API tools
    list_log_entries,
    # SLO listing
    list_slos,
    list_time_series,
    list_traces,
    perform_causal_analysis,
    # SLO prediction
    predict_slo_violation,
    query_promql,
    summarize_trace,
    validate_trace_quality,
)
from .tools.common import adk_tool
from .tools.common.telemetry import setup_telemetry
from .tools.config import get_tool_config_manager
from .tools.mcp.gcp import (
    create_bigquery_mcp_toolset,
    create_logging_mcp_toolset,
    create_monitoring_mcp_toolset,
    get_project_id_with_fallback,
    mcp_execute_sql,
    mcp_list_log_entries,
    mcp_list_timeseries,
    mcp_query_range,
)
from .tools.reporting import synthesize_report

# Initialize logger for this module
logger = logging.getLogger(__name__)

# Initialize standardized logging and telemetry
setup_telemetry()


def emojify_agent(agent: LlmAgent) -> LlmAgent:
    """Wraps an LlmAgent to add emojis to prompts and responses in logs.

    This ensures that regardless of how the agent is run (ADK CLI, custom server, etc.),
    the critical user-facing events are clearly visible in the logs.
    """
    original_run_async = agent.run_async

    @functools.wraps(original_run_async)
    async def wrapped_run_async(context: Any) -> AsyncGenerator[Any, None]:
        # 1. Log Prompt
        user_msg = "Unknown"
        if (
            hasattr(context, "user_content")
            and context.user_content
            and context.user_content.parts
        ):
            user_msg = context.user_content.parts[0].text

        # Determine project and session
        project_id = os.environ.get(
            "GOOGLE_CLOUD_PROJECT", os.environ.get("GCP_PROJECT_ID", "unknown")
        )
        session_id = (
            getattr(context.session, "id", "unknown")
            if hasattr(context, "session")
            else "unknown"
        )

        logging.info(f"💬 User Prompt: '{user_msg}'")
        logging.info(f"📍 Context: Project={project_id}, Session={session_id}")

        # 2. Run Original
        full_response_parts = []
        async for event in original_run_async(context):
            if hasattr(event, "content") and event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        full_response_parts.append(part.text)
            yield event

        # 3. Log Response
        final_response = "".join(full_response_parts)
        if final_response:
            preview = (
                final_response[:500] + "..."
                if len(final_response) > 500
                else final_response
            )
            logging.info(f"🏁 Final Response to User: '{preview}'")

    object.__setattr__(agent, "run_async", wrapped_run_async)
    return agent


# ============================================================================
# MCP Toolset Management
# ============================================================================

# Lazy-loaded MCP toolsets (created on first use in async context)
_bigquery_mcp_toolset: BaseToolset | None = None
_logging_mcp_toolset: BaseToolset | None = None
_monitoring_mcp_toolset: BaseToolset | None = None


async def _get_bigquery_mcp_toolset() -> BaseToolset | None:
    """Lazily create BigQuery MCP toolset in async context."""
    global _bigquery_mcp_toolset
    if _bigquery_mcp_toolset is None:
        _bigquery_mcp_toolset = create_bigquery_mcp_toolset()
    return _bigquery_mcp_toolset


async def _get_logging_mcp_toolset() -> BaseToolset | None:
    """Lazily create Cloud Logging MCP toolset in async context."""
    global _logging_mcp_toolset
    if _logging_mcp_toolset is None:
        _logging_mcp_toolset = create_logging_mcp_toolset()
    return _logging_mcp_toolset


async def _get_monitoring_mcp_toolset() -> BaseToolset | None:
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
    dataset_id: str | None = None,
    table_name: str | None = None,
    time_window_hours: int = 24,
    service_name: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Run Stage 0: Aggregate analysis using BigQuery.

    This is the entry point for fleet-wide analysis. It queries BigQuery telemetry tables
    to find statistical anomalies across thousands of traces.

    If `dataset_id` or `table_name` are not provided, this tool will automatically
    attempt to discover them using `discover_telemetry_sources`.

    Args:
        dataset_id: BigQuery dataset ID (e.g., 'your_project.telemetry_dataset'). Optional.
        table_name: Table name containing OTel spans (e.g., '_AllSpans'). Optional.
        time_window_hours: Lookback window in hours (default: 24).
        service_name: Optional filter to restrict analysis to a specific service.
        tool_context: ADK tool context (required for sub-agent execution).

    Returns:
        A dictionary containing:
        - "stage": "aggregate"
        - "status": "success" or "error"
        - "result": The output from the `aggregate_analyzer` sub-agent.
    """
    logger.info(
        f"🎺 Running aggregate analysis (Dataset: {dataset_id}, Table: {table_name})"
    )

    if tool_context is None:
        raise ValueError("tool_context is required")

    try:
        # 1. Auto-Discovery if needed
        if not dataset_id or not table_name:
            logger.info("Dataset or table not provided. Running discovery...")
            discovery_result = await discover_telemetry_sources(
                tool_context=tool_context
            )

            trace_table_full = discovery_result.get("trace_table")
            if not trace_table_full:
                return {
                    "stage": "aggregate",
                    "status": "success",
                    "result": "Telemetry discovery completed but found no trace tables. Please ask the user to provide the 'dataset_id' manually.",
                }

            # trace_table_full is likely "project.dataset.table"
            # We need to split it if possible, or just pass it as is to the prompt
            logger.info(f"Discovered trace table: {trace_table_full}")

            parts = trace_table_full.split(".")
            if len(parts) >= 3:
                dataset_id = f"{parts[0]}.{parts[1]}"
                table_name = parts[2]
            elif len(parts) == 2:
                dataset_id = parts[0]
                table_name = parts[1]
            else:
                # Fallback: just use what we have
                dataset_id = trace_table_full
                table_name = "_AllSpans"  # Default guess if parsing fails

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
    """Run Stage 1: Parallel triage analysis with the "Squad".

    This stage executes multiple specialized sub-agents in parallel to analyze
    specific traces. It acts as a "Council of Experts" where each agent looks
    at the problem through a different lens.

    Active Sub-Agents:
    - **Latency Analyzer**: Identifies critical path and bottlenecks.
    - **Error Analyzer**:  Investigates error codes, stack traces, and failure points.
    - **Structure Analyzer**: Compares call graph topology (new/missing spans).
    - **Statistics Analyzer**: Calculates z-scores and anomaly significance.
    - **Resiliency Architect**: Checks for retry storms, timeouts, and cascading failures.
    - **Log Analyst**: Checks for correlated log errors and anomalies.

    Args:
        baseline_trace_id: ID of a "good" trace (reference baseline).
        target_trace_id: ID of the "bad" trace (anomaly to investigate).
        project_id: GCP project ID (optional, uses env if not provided).
        tool_context: ADK tool context (required).

    Returns:
        A dictionary containing combined results from all sub-agents:
        {
            "stage": "triage",
            "results": {
                "latency": {...},
                "error": {...},
                "structure": {...},
                ...
            }
        }
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
        AgentTool(resiliency_architect).run_async(
            args={"request": prompt}, tool_context=tool_context
        ),
        AgentTool(log_analyst).run_async(
            args={"request": prompt}, tool_context=tool_context
        ),
        return_exceptions=True,
    )

    agent_names = [
        "latency",
        "error",
        "structure",
        "statistics",
        "resiliency",
        "log_analyst",
    ]
    triage_results: dict[str, dict[str, Any]] = {}

    for name, result in zip(agent_names, results, strict=False):
        if isinstance(result, Exception):
            logger.error(f"{name}_analyzer failed: {result}")
            triage_results[name] = {"status": "error", "error": str(result)}
        else:
            triage_results[name] = {"status": "success", "result": result}

    return {
        "stage": "triage",
        "baseline_trace_id": baseline_trace_id,
        "target_trace_id": target_trace_id,
        "results": triage_results,
    }


@adk_tool
async def run_deep_dive_analysis(
    baseline_trace_id: str,
    target_trace_id: str,
    triage_findings: dict[str, Any],
    project_id: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Run Stage 2: Deep Dive analysis.

    Synthesizes Stage 1 findings to determine causality, impact, and root cause.

    Active Sub-Agents:
    - **Causality Analyzer**: Correlates across signals to find the 'smoking gun'.
    - **Service Impact Analyzer**: Assesses upstream/downstream blast radius.
    - **Change Detective**: Correlates with deployments and config changes.

    Args:
        baseline_trace_id: Good trace ID.
        target_trace_id: Bad trace ID.
        triage_findings: Findings from Stage 1 (Triage).
        project_id: GCP project ID.
        tool_context: ADK tool context.

    Returns:
        Deep dive results.
    """
    if tool_context is None:
        raise ValueError("tool_context is required")

    if not project_id:
        project_id = get_project_id_with_fallback()

    logger.info(f"Running deep dive analysis for {target_trace_id}")

    prompt = f"""
Deep dive into the issue with target trace {target_trace_id}.
Baseline trace: {baseline_trace_id}
Triage findings: {triage_findings}
Project: {project_id}

Determine the root cause and impact.
"""

    results = await asyncio.gather(
        AgentTool(causality_analyzer).run_async(
            args={"request": prompt}, tool_context=tool_context
        ),
        AgentTool(service_impact_analyzer).run_async(
            args={"request": prompt}, tool_context=tool_context
        ),
        AgentTool(change_detective).run_async(
            args={"request": prompt}, tool_context=tool_context
        ),
        return_exceptions=True,
    )

    agent_names = ["causality", "impact", "change"]
    deep_dive_results: dict[str, dict[str, Any]] = {}

    for name, result in zip(agent_names, results, strict=False):
        if isinstance(result, Exception):
            logger.error(f"{name}_analyzer failed: {result}")
            deep_dive_results[name] = {"status": "error", "error": str(result)}
        else:
            deep_dive_results[name] = {"status": "success", "result": result}

    return {
        "stage": "deep_dive",
        "results": deep_dive_results,
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
    """Run log pattern analysis to find emergent issues.

    This function compares log patterns between two time periods using
    the Drain3 algorithm to identify NEW patterns that may identify issues.

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
        result = await AgentTool(log_analyst).run_async(
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
            "stage": "log_pattern",
            "status": "success",
            "result": result,
        }

    except Exception as e:
        logger.error(f"Log pattern analysis failed: {e}", exc_info=True)
        return {
            "stage": "log_pattern",
            "status": "error",
            "error": str(e),
        }


# ============================================================================
# Tool Registry for Configuration
# ============================================================================

TOOL_NAME_MAP = {
    # Observability
    "fetch_trace": fetch_trace,
    "list_log_entries": list_log_entries,
    "query_promql": query_promql,
    "list_slos": list_slos,
    "list_traces": list_traces,
    "get_logs_for_trace": get_logs_for_trace,
    "get_trace_by_url": get_trace_by_url,
    "summarize_trace": summarize_trace,
    "get_golden_signals": get_golden_signals,
    # Analysis
    "calculate_span_durations": calculate_span_durations,
    "find_bottleneck_services": find_bottleneck_services,
    "correlate_logs_with_trace": correlate_logs_with_trace,
    "analyze_critical_path": analyze_critical_path,
    "build_call_graph": build_call_graph,
    "build_service_dependency_graph": build_service_dependency_graph,
    "build_cross_signal_timeline": build_cross_signal_timeline,
    "analyze_trace_patterns": analyze_trace_patterns,
    "find_structural_differences": find_structural_differences,
    "find_hidden_dependencies": find_hidden_dependencies,
    # Metrics
    "detect_metric_anomalies": detect_metric_anomalies,
    "list_time_series": list_time_series,
    "compare_metric_windows": compare_metric_windows,
    "analyze_signal_correlation_strength": analyze_signal_correlation_strength,
    "analyze_error_budget_burn": analyze_error_budget_burn,
    "predict_slo_violation": predict_slo_violation,
    # GKE / Infrastructure
    "get_gke_cluster_health": get_gke_cluster_health,
    "analyze_node_conditions": analyze_node_conditions,
    "analyze_hpa_events": analyze_hpa_events,
    "get_pod_restart_events": get_pod_restart_events,
    "get_container_oom_events": get_container_oom_events,
    "get_workload_health_summary": get_workload_health_summary,
    # Alerts
    "list_alerts": list_alerts,
    "list_alert_policies": list_alert_policies,
    "get_alert": get_alert,
    # Advanced Diagnostics
    "perform_causal_analysis": perform_causal_analysis,
    "analyze_upstream_downstream_impact": analyze_upstream_downstream_impact,
    "correlate_trace_with_kubernetes": correlate_trace_with_kubernetes,
    "correlate_trace_with_metrics": correlate_trace_with_metrics,
    "calculate_series_stats": calculate_series_stats,
    "detect_trend_changes": detect_trend_changes,
    # Pattern Analysis
    "extract_log_patterns": extract_log_patterns,
    "compare_log_patterns": compare_log_patterns,
    "detect_all_sre_patterns": detect_all_sre_patterns,
    "analyze_log_anomalies": analyze_log_anomalies,
    # Root Cause
    "detect_cascading_timeout": detect_cascading_timeout,
    "detect_retry_storm": detect_retry_storm,
    "detect_connection_pool_issues": detect_connection_pool_issues,
    "detect_circular_dependencies": detect_circular_dependencies,
    "find_similar_past_incidents": find_similar_past_incidents,
    # Remediation
    "generate_remediation_suggestions": generate_remediation_suggestions,
    "estimate_remediation_risk": estimate_remediation_risk,
    "get_gcloud_commands": get_gcloud_commands,
    # Specialized Analysis
    "analyze_aggregate_metrics": analyze_aggregate_metrics,
    "calculate_critical_path_contribution": calculate_critical_path_contribution,
    "compare_span_timings": compare_span_timings,
    "compare_time_periods": compare_time_periods,
    "compute_latency_statistics": compute_latency_statistics,
    "correlate_incident_with_slo_impact": correlate_incident_with_slo_impact,
    "correlate_metrics_with_traces_via_exemplars": correlate_metrics_with_traces_via_exemplars,
    "detect_latency_anomalies": detect_latency_anomalies,
    "extract_errors": extract_errors,
    "find_example_traces": find_example_traces,
    "find_exemplar_traces": find_exemplar_traces,
    "get_current_time": get_current_time,
    "get_slo_status": get_slo_status,
    "list_error_events": list_error_events,
    "validate_trace_quality": validate_trace_quality,
    # MCP Tools
    "mcp_execute_sql": mcp_execute_sql,
    "mcp_list_log_entries": mcp_list_log_entries,
    "mcp_list_timeseries": mcp_list_timeseries,
    "mcp_query_range": mcp_query_range,
    # Discovery
    "discover_telemetry_sources": discover_telemetry_sources,
    # Reporting
    "synthesize_report": synthesize_report,
    # Orchestration
    "run_aggregate_analysis": run_aggregate_analysis,
    "run_triage_analysis": run_triage_analysis,
    "run_deep_dive_analysis": run_deep_dive_analysis,
    "run_log_pattern_analysis": run_log_pattern_analysis,
}

# Common tools for all agents
base_tools: list[Any] = [
    fetch_trace,
    list_log_entries,
    query_promql,
    list_slos,
    calculate_span_durations,
    find_bottleneck_services,
    correlate_logs_with_trace,
    get_gke_cluster_health,
    list_alerts,
    detect_metric_anomalies,
    analyze_signal_correlation_strength,
    # Log pattern tools
    extract_log_patterns,
    compare_log_patterns,
    analyze_log_anomalies,
    # Orchestration tools
    run_aggregate_analysis,
    run_triage_analysis,
    run_deep_dive_analysis,
    run_log_pattern_analysis,
]


def get_enabled_tools() -> list[Any]:
    """Get list of enabled tools based on configuration.

    Returns:
        List of tool functions that are currently enabled.
    """
    manager = get_tool_config_manager()
    enabled_tool_names = manager.get_enabled_tools()

    enabled_tools = []
    for tool_name in enabled_tool_names:
        if tool_name in TOOL_NAME_MAP:
            enabled_tools.append(TOOL_NAME_MAP[tool_name])

    logger.info(
        f"Loaded {len(enabled_tools)} enabled tools out of {len(TOOL_NAME_MAP)} total"
    )
    return enabled_tools


# ============================================================================
# Main Agent Definition
# ============================================================================

# Create the main SRE Agent
sre_agent = LlmAgent(
    name="sre_agent",
    model="gemini-2.5-flash",
    description="""SRE Agent - Google Cloud Observability & Reliability Expert.

Capabilities:
- Orchestrates a "Council of Experts" for multi-stage incident analysis (Aggregate -> Triage -> Deep Dive)
- Performs cross-signal correlation (Traces + Logs + Metrics) to find root causes
- Analyzes SLO/SLI status, error budgets, and predicts violations
- Debugs Kubernetes/GKE clusters (Node pressure, Pod crash loops, OOMs)
- Provides automated remediation suggestions with risk assessment

Structure:
- Stage 0 (Aggregate): Analyze fleet-wide trends using BigQuery
- Stage 1 (Triage): Parallel analysis of specific traces (Latency, Error, Structure, Stats)
- Stage 2 (Deep Dive): Causality, Impact Analysis, and Change Detection

Direct Tools:
- Observability: fetch_trace, list_log_entries, query_promql, list_slos
- Analysis: calculate_span_durations, find_bottleneck_services, correlate_logs_with_trace
- Platform: get_gke_cluster_health, list_alerts, detect_metric_anomalies""",
    instruction=SRE_AGENT_PROMPT,
    tools=base_tools,
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
        log_analyst,
        # Metrics analysis sub-agents
        metrics_analyzer,
        alert_analyst,
        # New Sub-Agents
        change_detective,
        resiliency_architect,
    ],
)

# Export as root_agent for ADK CLI compatibility
root_agent = emojify_agent(sre_agent)

# Emojify all sub-agents as well
aggregate_analyzer = emojify_agent(aggregate_analyzer)
latency_analyzer = emojify_agent(latency_analyzer)
error_analyzer = emojify_agent(error_analyzer)
structure_analyzer = emojify_agent(structure_analyzer)
statistics_analyzer = emojify_agent(statistics_analyzer)
causality_analyzer = emojify_agent(causality_analyzer)
service_impact_analyzer = emojify_agent(service_impact_analyzer)
log_analyst = emojify_agent(log_analyst)
metrics_analyzer = emojify_agent(metrics_analyzer)
alert_analyst = emojify_agent(alert_analyst)
change_detective = emojify_agent(change_detective)
resiliency_architect = emojify_agent(resiliency_architect)

# ============================================================================
# Dynamic Tool Loading
# ============================================================================


async def get_agent_with_mcp_tools(use_enabled_tools: bool = True) -> LlmAgent:
    """Creates an agent instance with MCP toolsets loaded.

    This should be called in an async context to properly initialize
    MCP toolsets. Use this for programmatic agent creation.

    Args:
        use_enabled_tools: If True, only include tools that are enabled in config.
                          If False, include all tools (base_tools).

    Returns:
        LlmAgent with MCP tools added.
    """
    # Get MCP toolsets
    bq_toolset = await _get_bigquery_mcp_toolset()
    logging_toolset = await _get_logging_mcp_toolset()
    monitoring_toolset = await _get_monitoring_mcp_toolset()

    # Get tools based on configuration
    if use_enabled_tools:
        all_tools = get_enabled_tools()
    else:
        all_tools = list(base_tools)

    # Add MCP toolsets if available
    if bq_toolset:
        all_tools.append(bq_toolset)
    if logging_toolset:
        all_tools.append(logging_toolset)
    if monitoring_toolset:
        all_tools.append(monitoring_toolset)

    # Create agent with all tools
    agent = LlmAgent(
        name="sre_agent",
        model="gemini-2.5-flash",
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
            log_analyst,
            # Metrics analysis sub-agents
            metrics_analyzer,
            alert_analyst,
            change_detective,
            resiliency_architect,
        ],
    )
    return emojify_agent(agent)
