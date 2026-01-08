"""Cloud Trace Analyzer - Simplified Root Agent Definition.

This module implements a streamlined three-stage analysis architecture
optimized for SRE troubleshooting:

Stage 0 (Aggregate Analysis):
    - aggregate_analyzer: BigQuery-powered analysis of trace data at scale

Stage 1 (Trace Investigation):
    - trace_investigator: Comprehensive analysis combining latency, error,
      structure, and statistical analysis in a single agent

Stage 2 (Root Cause Analysis):
    - root_cause_analyzer: Determines causality and service impact

Architecture Benefits:
- Reduced complexity: 3 agents instead of 7
- Faster execution: Less parallel coordination overhead
- Clearer workflow: Each stage has a single focused agent
- SRE-optimized: Pattern detection for common issues
"""

import functools
import json
import logging
import os

import google.auth
from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool, ToolContext
from google.adk.tools.api_registry import ApiRegistry

from .prompt_v2 import ROOT_AGENT_PROMPT
from .decorators import adk_tool
from .sub_agents.aggregate.agent import aggregate_analyzer
from .sub_agents.investigator.agent import trace_investigator
from .sub_agents.root_cause.agent import root_cause_analyzer
from .tools.bigquery_otel import (
    analyze_aggregate_metrics,
    compare_time_periods,
    correlate_logs_with_trace,
    detect_trend_changes,
    find_exemplar_traces,
)
from .tools.o11y_clients import (
    fetch_trace,
    find_example_traces,
    get_current_time,
    get_logs_for_trace,
    get_trace_by_url,
    list_traces,
)
from .tools.sre_patterns import (
    detect_all_sre_patterns,
    detect_cascading_timeout,
    detect_connection_pool_issues,
    detect_retry_storm,
)
from .tools.trace_analysis import summarize_trace, validate_trace_quality

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def _create_bigquery_mcp_toolset(project_id: str | None = None):
    """
    Creates a singleton BigQuery MCP toolset instance.

    The singleton pattern prevents MCP session timeout issues that occurred
    with per-request toolset creation.
    """
    if not project_id:
        try:
            _, project_id = google.auth.default()
            project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
        except Exception:
            pass

    if not project_id:
        logger.warning("No Project ID detected; MCP toolset will not be available")
        return None

    try:
        logger.info(f"Creating BigQuery MCP toolset for project: {project_id}")

        mcp_server_name = f"projects/{project_id}/locations/global/mcpServers/google-bigquery.googleapis.com-mcp"

        api_registry = ApiRegistry(
            project_id, header_provider=lambda _: {"x-goog-user-project": project_id}
        )

        mcp_toolset = api_registry.get_toolset(
            mcp_server_name=mcp_server_name,
            tool_filter=[
                "execute_sql",
                "list_dataset_ids",
                "list_table_ids",
                "get_table_info",
            ],
        )

        return mcp_toolset

    except Exception as e:
        logger.error(f"Failed to create BigQuery MCP toolset: {e}", exc_info=True)
        return None


def get_bigquery_mcp_toolset():
    """Factory function for BigQuery MCP toolset."""
    return _create_bigquery_mcp_toolset()


# Detect Project ID for instruction enrichment
project_id = None
try:
    _, project_id = google.auth.default()
    project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
except Exception:
    pass


# =============================================================================
# Stage 0: Aggregate Analysis - BigQuery-powered broad analysis
# =============================================================================
stage0_aggregate_analyzer = aggregate_analyzer
if project_id:
    stage0_aggregate_analyzer.instruction += (
        f"\n\nCurrent Project ID: {project_id}\n"
        "Use this for 'projectId' arguments in BigQuery tools."
    )

# =============================================================================
# Stage 1: Trace Investigation - Comprehensive trace analysis
# =============================================================================
stage1_trace_investigator = trace_investigator

# =============================================================================
# Stage 2: Root Cause Analysis - Causality and impact assessment
# =============================================================================
stage2_root_cause_analyzer = root_cause_analyzer


@adk_tool
async def run_aggregate_analysis(
    dataset_id: str,
    time_window_hours: int = 24,
    service_name: str | None = None,
    tool_context: ToolContext = None,
) -> dict:
    """
    Stage 0: Analyze traces at scale using BigQuery.

    Start broad - analyze thousands of traces to identify patterns,
    trends, and select exemplar traces for detailed investigation.

    Args:
        dataset_id: BigQuery dataset ID containing OpenTelemetry traces (e.g., 'project.dataset')
        time_window_hours: How many hours back to analyze (default 24h)
        service_name: Optional filter for specific service
        tool_context: The tool context provided by the ADK.

    Returns:
        Analysis report with health metrics, problem areas, and recommended trace IDs.
    """
    if tool_context is None:
        raise ValueError("tool_context is required for running sub-agents")

    stage0_input = {
        "dataset_id": dataset_id,
        "time_window_hours": time_window_hours,
        "service_name": service_name,
    }

    aggregate_tool = AgentTool(stage0_aggregate_analyzer)

    return await aggregate_tool.run_async(
        args={
            "request": (
                f"Context: {json.dumps(stage0_input)}\n"
                "Instruction: Perform aggregate analysis of trace data using BigQuery. "
                "Identify problem areas, detect trends, and select exemplar traces for investigation."
            )
        },
        tool_context=tool_context,
    )


@adk_tool
async def run_investigation(
    baseline_trace_id: str,
    target_trace_id: str,
    project_id: str | None = None,
    tool_context: ToolContext = None,
) -> dict:
    """
    Stage 1: Comprehensive trace investigation.

    Analyzes latency, errors, structure, and statistical patterns
    between baseline and target traces to identify WHAT is different.

    Args:
        baseline_trace_id: The ID of the normal/baseline trace.
        target_trace_id: The ID of the anomalous/target trace.
        project_id: The Google Cloud Project ID.
        tool_context: The tool context provided by the ADK.

    Returns:
        Investigation report with latency, error, and structural findings.
    """
    if tool_context is None:
        raise ValueError("tool_context is required for running sub-agents")

    stage1_input = {
        "baseline_trace_id": baseline_trace_id,
        "target_trace_id": target_trace_id,
        "project_id": project_id,
    }

    investigator_tool = AgentTool(stage1_trace_investigator)
    return await investigator_tool.run_async(
        args={
            "request": (
                f"Context: {json.dumps(stage1_input)}\n"
                "Instruction: Perform comprehensive trace investigation comparing "
                "baseline and target traces. Analyze latency, errors, structure, "
                "and statistical patterns."
            )
        },
        tool_context=tool_context,
    )


@adk_tool
async def run_root_cause_analysis(
    baseline_trace_id: str,
    target_trace_id: str,
    investigation_report: str,
    project_id: str | None = None,
    tool_context: ToolContext = None,
) -> dict:
    """
    Stage 2: Root cause and impact analysis.

    Determines WHY issues occurred, traces causal chains, and
    assesses service-level blast radius.

    Args:
        baseline_trace_id: The ID of the normal/baseline trace.
        target_trace_id: The ID of the anomalous/target trace.
        investigation_report: The report from Stage 1 investigation.
        project_id: The Google Cloud Project ID.
        tool_context: The tool context provided by the ADK.

    Returns:
        Root cause analysis with causal chain and impact assessment.
    """
    if tool_context is None:
        raise ValueError("tool_context is required for running sub-agents")

    stage2_input = {
        "baseline_trace_id": baseline_trace_id,
        "target_trace_id": target_trace_id,
        "investigation_report": investigation_report,
        "project_id": project_id,
    }

    root_cause_tool = AgentTool(stage2_root_cause_analyzer)
    return await root_cause_tool.run_async(
        args={
            "request": (
                f"Context: {json.dumps(stage2_input)}\n"
                "Instruction: Using the investigation report, perform root cause "
                "analysis to determine why issues occurred and assess service impact."
            )
        },
        tool_context=tool_context,
    )


# =============================================================================
# Tool Configuration
# =============================================================================
base_tools = [
    # === Stage Orchestration Tools ===
    run_aggregate_analysis,  # Stage 0: BigQuery aggregate analysis
    run_investigation,  # Stage 1: Trace investigation
    run_root_cause_analysis,  # Stage 2: Root cause analysis
    # === Direct Trace Tools (for quick queries) ===
    fetch_trace,
    list_traces,
    find_example_traces,
    get_trace_by_url,
    summarize_trace,
    validate_trace_quality,
    get_current_time,
    # === Observability Tools ===
    get_logs_for_trace,
    # === BigQuery Analysis Tools ===
    analyze_aggregate_metrics,
    find_exemplar_traces,
    compare_time_periods,
    detect_trend_changes,
    correlate_logs_with_trace,
    # === SRE Pattern Detection Tools ===
    detect_all_sre_patterns,
    detect_retry_storm,
    detect_cascading_timeout,
    detect_connection_pool_issues,
]

# Add MCP toolset if available
mcp_toolset = get_bigquery_mcp_toolset()
if mcp_toolset:
    base_tools.append(mcp_toolset)
    stage0_aggregate_analyzer.tools.append(mcp_toolset)

# Build final instruction
final_instruction = ROOT_AGENT_PROMPT
if project_id:
    final_instruction += (
        f"\n\nCurrent Project ID: {project_id}\n"
        "Use this for 'projectId' arguments in tool calls."
    )

# =============================================================================
# Root Agent Definition
# =============================================================================
trace_analyzer_agent = LlmAgent(
    name="trace_analyzer_agent",
    model="gemini-2.5-pro",
    description=(
        "SRE Assistant for distributed trace analysis. Orchestrates investigation "
        "and root cause analysis to help engineers identify and resolve performance issues."
    ),
    instruction=final_instruction,
    output_key="trace_analysis_report",
    tools=base_tools,
)

# Expose as root_agent for ADK CLI compatibility
root_agent = trace_analyzer_agent
