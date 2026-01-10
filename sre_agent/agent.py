"""SRE Agent - Google Cloud Observability Analysis Agent.

This is the main agent for SRE tasks, specializing in analyzing telemetry data
from Google Cloud Observability: traces, logs, and metrics.

The agent uses a hierarchical architecture for trace analysis:
- Stage 0 (Aggregate): BigQuery-powered analysis of thousands of traces
- Stage 1 (Triage): Parallel analysis with 4 specialized sub-agents
- Stage 2 (Deep Dive): Root cause and impact analysis

For other tasks (logs, metrics), the agent uses direct tools.
"""

import asyncio
import logging
import os
from typing import Any

import google.auth
from google.adk.agents import LlmAgent
from google.adk.tools import ToolContext

from .prompt import SRE_AGENT_PROMPT
from .tools import (
    # Trace tools
    fetch_trace,
    list_traces,
    find_example_traces,
    get_trace_by_url,
    calculate_span_durations,
    extract_errors,
    build_call_graph,
    summarize_trace,
    validate_trace_quality,
    compare_span_timings,
    find_structural_differences,
    # GCP direct API tools
    list_log_entries,
    list_time_series,
    list_error_events,
    get_logs_for_trace,
    get_current_time,
    # BigQuery tools
    analyze_aggregate_metrics,
    find_exemplar_traces,
    compare_time_periods,
    detect_trend_changes,
    correlate_logs_with_trace,
)
from .tools.gcp.mcp import (
    create_bigquery_mcp_toolset,
    create_logging_mcp_toolset,
    create_monitoring_mcp_toolset,
    mcp_list_log_entries,
    mcp_list_timeseries,
    mcp_query_range,
    get_project_id_with_fallback,
)

# Import sub-agents for trace analysis
from .sub_agents import (
    aggregate_analyzer,
    latency_analyzer,
    error_analyzer,
    structure_analyzer,
    statistics_analyzer,
    causality_analyzer,
    service_impact_analyzer,
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
    list_error_events,
    get_logs_for_trace,
    get_current_time,
    # BigQuery OTel tools
    analyze_aggregate_metrics,
    find_exemplar_traces,
    compare_time_periods,
    detect_trend_changes,
    correlate_logs_with_trace,
    # MCP tools (wrapper functions)
    mcp_list_log_entries,
    mcp_list_timeseries,
    mcp_query_range,
]


# ============================================================================
# Orchestration Functions
# ============================================================================


async def run_aggregate_analysis(
    dataset_id: str,
    table_name: str,
    time_window_hours: int = 24,
    service_name: str | None = None,
    tool_context: ToolContext = None,
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

    try:
        # Run aggregate analyzer sub-agent
        result = await aggregate_analyzer.run_async(
            user_content=f"""
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


async def run_triage_analysis(
    baseline_trace_id: str,
    target_trace_id: str,
    project_id: str | None = None,
    tool_context: ToolContext = None,
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
        latency_analyzer.run_async(user_content=prompt, tool_context=tool_context),
        error_analyzer.run_async(user_content=prompt, tool_context=tool_context),
        structure_analyzer.run_async(user_content=prompt, tool_context=tool_context),
        statistics_analyzer.run_async(user_content=prompt, tool_context=tool_context),
        return_exceptions=True,
    )

    agent_names = ["latency", "error", "structure", "statistics"]
    triage_results = {}

    for name, result in zip(agent_names, results):
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


async def run_deep_dive_analysis(
    baseline_trace_id: str,
    target_trace_id: str,
    triage_findings: dict[str, Any],
    project_id: str | None = None,
    tool_context: ToolContext = None,
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
        causality_analyzer.run_async(user_content=prompt, tool_context=tool_context),
        service_impact_analyzer.run_async(user_content=prompt, tool_context=tool_context),
        return_exceptions=True,
    )

    agent_names = ["causality", "service_impact"]
    deep_dive_results = {}

    for name, result in zip(agent_names, results):
        if isinstance(result, Exception):
            logger.error(f"{name}_analyzer failed: {result}")
            deep_dive_results[name] = {"status": "error", "error": str(result)}
        else:
            deep_dive_results[name] = {"status": "success", "result": result}

    return {
        "stage": "deep_dive",
        "results": deep_dive_results,
    }


# ============================================================================
# Main Agent Definition
# ============================================================================

# Create the main SRE Agent
sre_agent = LlmAgent(
    name="sre_agent",
    model="gemini-2.5-pro",
    description=(
        "SRE Agent for Google Cloud Observability. Analyzes traces, logs, and metrics "
        "to diagnose production issues. Specializes in distributed trace analysis with "
        "multi-stage investigation: aggregate analysis, triage, and deep dive."
    ),
    instruction=SRE_AGENT_PROMPT,
    tools=base_tools,
    # Sub-agents for specialized analysis (automatically invoked based on task)
    sub_agents=[
        aggregate_analyzer,
        latency_analyzer,
        error_analyzer,
        structure_analyzer,
        statistics_analyzer,
        causality_analyzer,
        service_impact_analyzer,
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
            aggregate_analyzer,
            latency_analyzer,
            error_analyzer,
            structure_analyzer,
            statistics_analyzer,
            causality_analyzer,
            service_impact_analyzer,
        ],
    )
