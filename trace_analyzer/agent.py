"""Cloud Trace Analyzer - Root Agent Definition.

This module implements a two-stage hierarchical analysis architecture:

Stage 1 (Triage Squad):
    - latency_analyzer: Quick span timing comparison
    - error_analyzer: Error detection and comparison
    - structure_analyzer: Call graph topology changes

    Purpose: Rapidly identify WHAT is different between traces.

Stage 2 (Deep Dive Squad):
    - statistics_analyzer: Statistical distribution analysis
    - causality_analyzer: Root cause determination
    - service_impact_analyzer: Blast radius assessment

    Purpose: Deeply analyze WHY the differences matter and WHERE to focus.

The root agent orchestrates both stages, using Stage 1 results to guide
Stage 2 analysis for efficient, targeted investigation.
"""

import json
from google.adk.agents import LlmAgent, ParallelAgent
from google.adk.tools import AgentTool, ToolContext

from .decorators import adk_tool

from . import prompt
from .tools.trace_client import (
    find_example_traces,
    fetch_trace,
    list_traces,
    get_trace_by_url,
    get_current_time,
    list_log_entries,
    list_time_series,
    list_error_events,
    get_logs_for_trace,
)
from .tools.trace_analysis import summarize_trace, validate_trace_quality
from .tools.statistical_analysis import analyze_trace_patterns
from .sub_agents.latency.agent import latency_analyzer
from .sub_agents.error.agent import error_analyzer
from .sub_agents.structure.agent import structure_analyzer
from .sub_agents.statistics.agent import statistics_analyzer
from .sub_agents.causality.agent import causality_analyzer
from .sub_agents.service_impact.agent import service_impact_analyzer
from .tools.trace_filter import (
    select_traces_from_error_reports,
    select_traces_from_monitoring_alerts,
    select_traces_from_statistical_outliers,
    select_traces_manually,
)

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




import os
import google.auth
from google.adk.tools.api_registry import ApiRegistry
from google.adk.tools.base_toolset import BaseToolset

class LazyMcpRegistryToolset(BaseToolset):
    """Lazily initializes the ApiRegistry and McpToolset to ensure session creation happens in the correct event loop."""
    def __init__(self, project_id: str, mcp_server_name: str, tool_filter: list[str]):
        self.project_id = project_id
        self.mcp_server_name = mcp_server_name
        self.tool_filter = tool_filter
        self.tool_name_prefix = None
        self._inner_toolset = None
        
    async def get_tools(self, readonly_context=None):
        if not self._inner_toolset:
            # Initialize ApiRegistry lazily in the running event loop
            api_registry = ApiRegistry(self.project_id)
            self._inner_toolset = api_registry.get_toolset(
                mcp_server_name=self.mcp_server_name,
                tool_filter=self.tool_filter
            )
        return await self._inner_toolset.get_tools()

def load_mcp_tools():
    """Loads tools from configured MCP endpoints."""
    tools = []
    
    # 1. Google Cloud BigQuery MCP Endpoint via ApiRegistry
    try:
        # Get default project if not set, or use env var
        _, project_id = google.auth.default()
        # Fallback to env var if default auth doesn't provide project_id (e.g. running locally with user creds sometimes)
        project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
        
        if project_id:
            # Pattern: projects/{project}/locations/global/mcpServers/{server_id}
            mcp_server_name = f"projects/{project_id}/locations/global/mcpServers/google-bigquery.googleapis.com-mcp"
            
            # Use LazyMcpRegistryToolset to avoid creating aiohttp sessions at module import time
            # which causes crashes in ASGI/uvicorn environments (especially with forking).
            bq_lazy_toolset = LazyMcpRegistryToolset(
                project_id=project_id,
                mcp_server_name=mcp_server_name,
                tool_filter=["execute_sql", "list_dataset_ids", "list_table_ids", "get_table_info"]
            )
            # Add the toolset directly. LlmAgent will call get_tools() on it.
            tools.append(bq_lazy_toolset)
            
    except Exception as e:
        print(f"Warning: Failed to setup BigQuery MCP tools: {e}")

    # 2. MCP Toolbox for Databases (Local/Self-hosted or Cloud Run)
    toolbox_url = os.environ.get("TOOLBOX_MCP_URL")
    if toolbox_url:
        try:
            # Use authenticated HTTP client
            from google.auth import default as google_auth_default
            from google.auth.transport.requests import Request
            from toolbox_core import ToolboxSyncClient

            creds, _ = google_auth_default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
            creds.refresh(Request())

            # Create client with auth headers
            toolbox_client = ToolboxSyncClient(
                toolbox_url,
                headers={'Authorization': f'Bearer {creds.token}'}
            )

            if hasattr(toolbox_client, 'list_tools'):
                tools.extend(toolbox_client.list_tools())
                print(f"Successfully loaded tools from Toolbox MCP at {toolbox_url}")

        except Exception as e:
            print(f"Warning: Failed to setup Toolbox MCP tools: {e}")
        
    return tools




@adk_tool
async def run_two_stage_analysis(
    baseline_trace_id: str,
    target_trace_id: str,
    project_id: str = None,
    tool_context: ToolContext = None,
) -> dict:
    """
    Orchestrates a two-stage analysis (Triage -> Deep Dive) on two traces.

    Args:
        baseline_trace_id: The ID of the normal/baseline trace.
        target_trace_id: The ID of the anomalous/target trace.
        project_id: The Google Cloud Project ID.
        tool_context: The tool context provided by the ADK.

    Returns:
        A dictionary containing the combined analysis reports.
    """
    if tool_context is None:
        # This handles local testing or direct calls where context might be missing,
        # but in ADK execution it should be provided.
        # We can't easily run sub-agents without context via AgentTool, 
        # so we might need to error or mock.
        raise ValueError("tool_context is required for running sub-agents")

    stage1_input = {
        "baseline_trace_id": baseline_trace_id,
        "target_trace_id": target_trace_id,
        "project_id": project_id,
    }
    
    # Run Stage 1: Triage
    # We use AgentTool to wrap and run the agent, enabling it to access the current session/context.
    triage_tool = AgentTool(stage1_triage_squad)
    stage1_response = await triage_tool.run_async(
        args={"request": f"Context: {json.dumps(stage1_input)}\nInstruction: Analyze the traces provided."},
        tool_context=tool_context
    )
    
    # AgentTool returns the result as string (processed by output schema if valid, or text).
    # ParallelAgent usually returns text combined from sub-agents.
    stage1_report = stage1_response

    stage2_input = {
        "baseline_trace_id": baseline_trace_id,
        "target_trace_id": target_trace_id,
        "stage1_report": stage1_report,
        "project_id": project_id,
    }

    # Run Stage 2: Deep Dive
    deep_dive_tool = AgentTool(stage2_deep_dive_squad)
    stage2_response = await deep_dive_tool.run_async(
        args={
            "request": (
                f"Context: {json.dumps(stage2_input)}\n"
                "Instruction: Using the Stage 1 triage report, perform a deep-dive analysis "
                "to determine root cause and service impact."
            )
        },
        tool_context=tool_context
    )
    stage2_report = stage2_response

    return {
        "stage1_triage_report": stage1_report,
        "stage2_deep_dive_report": stage2_report,
    }
# Initialize base tools
base_tools = [
    # Two-stage analysis architecture
    run_two_stage_analysis,
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

# Load MCP tools
mcp_tools = load_mcp_tools()


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
    tools=base_tools + mcp_tools,
)

# Expose as root_agent for ADK CLI compatibility
root_agent = trace_analyzer_agent
