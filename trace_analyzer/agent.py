"""Cloud Trace Analyzer - Root Agent Definition.

This module implements a three-stage hierarchical analysis architecture:

Stage 0 (Aggregate Analysis):
    - aggregate_analyzer: BigQuery-powered analysis of trace data at scale

    Purpose: Start broad - analyze thousands of traces to identify patterns,
    trends, and select exemplar traces for detailed investigation.

Stage 1 (Triage Squad):
    - latency_analyzer: Quick span timing comparison
    - error_analyzer: Error detection and comparison
    - structure_analyzer: Call graph topology changes
    - statistics_analyzer: Statistical distribution analysis

    Purpose: Rapidly identify WHAT is different between traces.

Stage 2 (Deep Dive Squad):
    - causality_analyzer: Root cause determination
    - service_impact_analyzer: Blast radius assessment

    Purpose: Deeply analyze WHY the differences matter and WHERE to focus.

The root agent orchestrates all three stages:
1. Aggregate Analysis (BigQuery) → identify patterns and select exemplars
2. Triage Analysis (Trace API) → compare specific traces
3. Deep Dive Analysis → determine root cause and impact
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

import google.auth
from google.adk.agents import LlmAgent, ParallelAgent
from google.adk.tools import AgentTool, ToolContext
from google.adk.tools.api_registry import ApiRegistry
from google.adk.tools.base_toolset import BaseToolset

from . import prompt, telemetry  # Register logging filters
from .decorators import adk_tool
from .sub_agents.aggregate.agent import aggregate_analyzer
from .sub_agents.causality.agent import causality_analyzer
from .sub_agents.error.agent import error_analyzer
from .sub_agents.latency.agent import latency_analyzer
from .sub_agents.service_impact.agent import service_impact_analyzer
from .sub_agents.statistics.agent import statistics_analyzer
from .sub_agents.structure.agent import structure_analyzer
from .tools.bigquery_otel import (
    analyze_aggregate_metrics,
    compare_time_periods,
    correlate_logs_with_trace,
    detect_trend_changes,
    find_exemplar_traces,
)
from .tools.statistical_analysis import analyze_trace_patterns
from .tools.trace_analysis import summarize_trace, validate_trace_quality
from .tools.trace_client import (
    fetch_trace,
    find_example_traces,
    get_current_time,
    get_logs_for_trace,
    get_trace_by_url,
    list_error_events,
    list_log_entries,
    list_time_series,
    list_traces,
)
from .tools.trace_filter import (
    select_traces_from_error_reports,
    select_traces_from_monitoring_alerts,
    select_traces_from_statistical_outliers,
    select_traces_manually,
)

# =============================================================================
# Stage 0: Aggregate Analysis - BigQuery-powered broad analysis
# =============================================================================
# This is a single agent (not parallel) that uses BigQuery to analyze at scale
stage0_aggregate_analyzer = aggregate_analyzer

# =============================================================================
# Stage 1: Triage Squad - Quick identification of differences
# =============================================================================
stage1_triage_squad = ParallelAgent(
    name="stage1_triage_squad",
    sub_agents=[
        latency_analyzer,
        error_analyzer,
        structure_analyzer,
        statistics_analyzer,
    ],
    description=(
        "Stage 1 Triage: Runs 4 parallel analyzers to quickly identify "
        "latency differences, error changes, and structural modifications "
        "between baseline and target traces. Use this first to understand "
        "WHAT is different."
    ),
)

# =============================================================================
# Stage 2: Deep Dive Squad - Root cause and impact analysis
# =============================================================================
stage2_deep_dive_squad = ParallelAgent(
    name="stage2_deep_dive_squad",
    sub_agents=[
        causality_analyzer,
        service_impact_analyzer,
    ],
    description=(
        "Stage 2 Deep Dive: Runs 2 parallel analyzers for "
        "root cause determination, and service impact assessment. Use this after "
        "Stage 1 to understand WHY differences occurred and their blast radius."
    ),
)


def create_bigquery_mcp_toolset(project_id: str):
    """
    Creates BigQuery MCP toolset following the pattern from Google Cloud blog post:
    https://cloud.google.com/blog/products/data-analytics/using-the-fully-managed-remote-bigquery-mcp-server-to-build-data-ai-agents/

    SIMPLIFIED APPROACH (following official Google Cloud guidance):

    Key Principles:
    1. Create toolset ONCE (not per-request)
    2. Pass toolset directly to agent (not extracted tools)
    3. Let ADK framework handle lifecycle (no manual cleanup)
    4. Toolset is stateful and reusable across agent invocations

    This avoids the async task scope errors by:
    - Not manually calling get_tools() or close()
    - Letting the agent framework manage the toolset lifecycle
    - Toolset creation is synchronous (no async context issues)

    Args:
        project_id: Google Cloud project ID for BigQuery access

    Returns:
        Toolset instance to pass directly to agent's tools list
    """
    if not project_id:
        logger.warning("No Project ID provided; cannot create BigQuery MCP toolset")
        return None

    try:
        logger.info(f"Creating BigQuery MCP toolset for project: {project_id}")

        # Pattern: projects/{project}/locations/global/mcpServers/{server_id}
        mcp_server_name = f"projects/{project_id}/locations/global/mcpServers/google-bigquery.googleapis.com-mcp"

        # Create ApiRegistry with explicit quota project header
        api_registry = ApiRegistry(
            project_id,
            header_provider=lambda _: {"x-goog-user-project": project_id}
        )

        # Get the MCP toolset (this is synchronous, returns a toolset object)
        mcp_toolset = api_registry.get_toolset(
            mcp_server_name=mcp_server_name,
            tool_filter=["execute_sql", "list_dataset_ids", "list_table_ids", "get_table_info"]
        )

        logger.info("Successfully created BigQuery MCP toolset")
        return mcp_toolset

    except Exception as e:
        logger.error(f"Failed to create BigQuery MCP toolset: {e}", exc_info=True)
        return None




@adk_tool
async def run_aggregate_analysis(
    dataset_id: str,
    time_window_hours: int = 24,
    service_name: str | None = None,
    tool_context: ToolContext = None,
) -> dict:
    """
    Stage 0: Runs the Aggregate Analyzer to analyze traces at scale using BigQuery.

    This is the first step in SRE investigation: start broad to identify patterns,
    trends, and select exemplar traces for detailed comparison.

    Args:
        dataset_id: BigQuery dataset ID containing OpenTelemetry traces (e.g., 'project.dataset')
        time_window_hours: How many hours back to analyze (default 24h)
        service_name: Optional filter for specific service
        tool_context: The tool context provided by the ADK.

    Returns:
        Analysis report with health metrics, problem areas, timeline, and recommended trace IDs.
    """
    if tool_context is None:
        raise ValueError("tool_context is required for running sub-agents")

    stage0_input = {
        "dataset_id": dataset_id,
        "time_window_hours": time_window_hours,
        "service_name": service_name,
    }

    # Detect Project ID for instruction
    project_id = None
    try:
        _, project_id = google.auth.default()
        project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
    except:
        pass

    # Create MCP toolset (following blog post pattern: create once, pass directly)
    mcp_toolset = create_bigquery_mcp_toolset(project_id)

    instruction = stage0_aggregate_analyzer.instruction
    if project_id:
        instruction += f"\n\nCurrent Project ID: {project_id}\nUse this for 'projectId' arguments in BigQuery tools."

    # Create a fresh agent instance with merged tools
    original_tools = stage0_aggregate_analyzer.tools or []

    # Build tools list: add toolset if available (ADK will call get_tools() internally)
    agent_tools = original_tools.copy()
    if mcp_toolset:
        agent_tools.append(mcp_toolset)

    fresh_aggregate_analyzer = LlmAgent(
        name=stage0_aggregate_analyzer.name,
        model=stage0_aggregate_analyzer.model,
        description=stage0_aggregate_analyzer.description,
        instruction=instruction,
        # Pass toolset directly - ADK framework handles lifecycle
        tools=agent_tools
    )

    aggregate_tool = AgentTool(fresh_aggregate_analyzer)

    # No try/finally needed - ADK framework manages toolset lifecycle
    return await aggregate_tool.run_async(
        args={
            "request": (
                f"Context: {json.dumps(stage0_input)}\n"
                "Instruction: Perform aggregate analysis of trace data using BigQuery. "
                "Identify problem areas, detect trends, and select exemplar traces for investigation."
            )
        },
        tool_context=tool_context
    )


@adk_tool
async def run_triage_analysis(
    baseline_trace_id: str,
    target_trace_id: str,
    project_id: str | None = None,
    tool_context: ToolContext = None,
) -> dict:
    """
    Stage 1: Runs the Triage Squad (Latency, Error, Structure, Stats) to identify WHAT is different.

    Args:
        baseline_trace_id: The ID of the normal/baseline trace.
        target_trace_id: The ID of the anomalous/target trace.
        project_id: The Google Cloud Project ID.
        tool_context: The tool context provided by the ADK.
    """
    if tool_context is None:
        raise ValueError("tool_context is required for running sub-agents")

    stage1_input = {
        "baseline_trace_id": baseline_trace_id,
        "target_trace_id": target_trace_id,
        "project_id": project_id,
    }

    triage_tool = AgentTool(stage1_triage_squad)
    return await triage_tool.run_async(
        args={"request": f"Context: {json.dumps(stage1_input)}\nInstruction: Analyze the traces provided."},
        tool_context=tool_context
    )


@adk_tool
async def run_deep_dive_analysis(
    baseline_trace_id: str,
    target_trace_id: str,
    stage1_report: str,
    project_id: str | None = None,
    tool_context: ToolContext = None,
) -> dict:
    """
    Stage 2: Runs the Deep Dive Squad (Causality, Service Impact) to determine WHY issues occurred.

    Args:
        baseline_trace_id: The ID of the normal/baseline trace.
        target_trace_id: The ID of the anomalous/target trace.
        stage1_report: The text report from the Stage 1 Triage analysis.
        project_id: The Google Cloud Project ID.
        tool_context: The tool context provided by the ADK.
    """
    if tool_context is None:
        raise ValueError("tool_context is required for running sub-agents")

    stage2_input = {
        "baseline_trace_id": baseline_trace_id,
        "target_trace_id": target_trace_id,
        "stage1_report": stage1_report,
        "project_id": project_id,
    }

    deep_dive_tool = AgentTool(stage2_deep_dive_squad)
    return await deep_dive_tool.run_async(
        args={
            "request": (
                f"Context: {json.dumps(stage2_input)}\n"
                "Instruction: Using the Stage 1 triage report, perform a deep-dive analysis "
                "to determine root cause and service impact."
            )
        },
        tool_context=tool_context
    )
# Initialize base tools
base_tools = [
    # Three-stage analysis architecture
    run_aggregate_analysis,  # Stage 0: BigQuery aggregate analysis
    run_triage_analysis,     # Stage 1: Trace diff analysis
    run_deep_dive_analysis,  # Stage 2: Root cause analysis
    # BigQuery-powered OpenTelemetry tools
    analyze_aggregate_metrics,
    find_exemplar_traces,
    compare_time_periods,
    detect_trend_changes,
    correlate_logs_with_trace,
    # Trace selection tools
    select_traces_from_error_reports,
    select_traces_from_monitoring_alerts,
    select_traces_from_statistical_outliers,
    select_traces_manually,
    # Data source tools
    find_example_traces,
    fetch_trace,
    list_traces,
    get_trace_by_url,
    summarize_trace,
    validate_trace_quality,
    analyze_trace_patterns,
    get_current_time,
    list_log_entries,
    list_time_series,
    list_error_events,
    get_logs_for_trace,
]

# Note: MCP toolsets are created per-request in run_aggregate_analysis() and passed
# directly to the agent (following Google Cloud blog post pattern). The ADK framework
# handles toolset lifecycle automatically - no manual cleanup needed.
# This avoids "cancel scope in different task" errors.

# Detect Project ID for instruction
try:
    _, project_id = google.auth.default()
    project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
except Exception:
    project_id = None

final_instruction = prompt.ROOT_AGENT_PROMPT
if project_id:
    final_instruction += f"\n\nCurrent Project ID: {project_id}\nUse this for 'projectId' arguments in BigQuery tools."

trace_analyzer_agent = LlmAgent(
    name="trace_analyzer_agent",
    model="gemini-2.5-pro",
    description="Orchestrates a team of trace analysis specialists to perform diff analysis between distributed traces.",
    instruction=final_instruction,
    output_key="trace_analysis_report",
    tools=base_tools,
)

# Expose as root_agent for ADK CLI compatibility
root_agent = trace_analyzer_agent
