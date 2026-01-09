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

GCP MCP Tools Architecture:
    This module provides generic MCP tools for interacting with GCP observability services:
    - BigQuery: run_aggregate_analysis → google-bigquery.googleapis.com-mcp
    - Cloud Logging: run_logging_query → logging.googleapis.com-mcp
    - Cloud Monitoring: run_monitoring_query → monitoring.googleapis.com-mcp
    - Cloud Trace: Uses direct API client (no MCP server available)

    MCP server URLs can be overridden via environment variables:
    - BIGQUERY_MCP_SERVER (default: google-bigquery.googleapis.com-mcp)
    - LOGGING_MCP_SERVER (default: logging.googleapis.com-mcp)
    - MONITORING_MCP_SERVER (default: monitoring.googleapis.com-mcp)
"""

import asyncio
import json
import logging
import os


import google.auth
from google.adk.agents import LlmAgent, ParallelAgent
from google.adk.tools import AgentTool, ToolContext
from google.adk.tools.api_registry import ApiRegistry
from google.adk.tools.base_toolset import BaseToolset

from . import prompt  # Register logging filters
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
from .tools.o11y_clients import (
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

logger = logging.getLogger(__name__)


def _get_project_id_with_fallback() -> str | None:
    """Get project ID from environment or default credentials."""
    project_id = None
    try:
        _, project_id = google.auth.default()
        project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
    except Exception:
        pass
    return project_id


def _create_bigquery_mcp_toolset(project_id: str | None = None):
    """
    Creates a new instance of the BigQuery MCP toolset.

    NOTE: This function should be called in an async context (within an async
    function) to ensure proper MCP session lifecycle management. Creating the
    toolset at module import time causes "Attempted to exit cancel scope in a
    different task" errors because anyio cancel scopes cannot cross task boundaries.
    """
    if not project_id:
        project_id = _get_project_id_with_fallback()

    if not project_id:
        logger.warning(
            "No Project ID detected; MCP toolset will not be available"
        )
        return None

    try:
        logger.info(
            f"Creating BigQuery MCP toolset for project: {project_id}"
        )

        # Pattern: projects/{project}/locations/global/mcpServers/{server_id}
        # Allow override via environment variable
        default_server = "google-bigquery.googleapis.com-mcp"
        mcp_server = os.environ.get("BIGQUERY_MCP_SERVER", default_server)
        mcp_server_name = f"projects/{project_id}/locations/global/mcpServers/{mcp_server}"

        # Create ApiRegistry with explicit quota project header
        api_registry = ApiRegistry(
            project_id, header_provider=lambda _: {"x-goog-user-project": project_id}
        )

        # Get the MCP toolset - this creates a new session
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
        logger.error(
            f"Failed to create BigQuery MCP toolset: {e}", exc_info=True
        )
        return None


def _create_logging_mcp_toolset(project_id: str | None = None):
    """
    Creates a new instance of the Cloud Logging MCP toolset.

    NOTE: This function should be called in an async context (within an async
    function) to ensure proper MCP session lifecycle management.

    Environment variable override:
        LOGGING_MCP_SERVER: Override the default MCP server (default: logging.googleapis.com-mcp)
    """
    if not project_id:
        project_id = _get_project_id_with_fallback()

    if not project_id:
        logger.warning(
            "No Project ID detected; Cloud Logging MCP toolset will not be available"
        )
        return None

    try:
        logger.info(
            f"Creating Cloud Logging MCP toolset for project: {project_id}"
        )

        # Allow override via environment variable
        default_server = "logging.googleapis.com-mcp"
        mcp_server = os.environ.get("LOGGING_MCP_SERVER", default_server)
        mcp_server_name = f"projects/{project_id}/locations/global/mcpServers/{mcp_server}"

        # Create ApiRegistry with explicit quota project header
        api_registry = ApiRegistry(
            project_id, header_provider=lambda _: {"x-goog-user-project": project_id}
        )

        # Get the MCP toolset - this creates a new session
        mcp_toolset = api_registry.get_toolset(
            mcp_server_name=mcp_server_name,
            tool_filter=[
                "list_log_entries",
                "list_logs",
                "list_resource_descriptors",
            ],
        )

        return mcp_toolset

    except Exception as e:
        logger.error(
            f"Failed to create Cloud Logging MCP toolset: {e}", exc_info=True
        )
        return None


def _create_monitoring_mcp_toolset(project_id: str | None = None):
    """
    Creates a new instance of the Cloud Monitoring MCP toolset.

    NOTE: This function should be called in an async context (within an async
    function) to ensure proper MCP session lifecycle management.

    Environment variable override:
        MONITORING_MCP_SERVER: Override the default MCP server (default: monitoring.googleapis.com-mcp)
    """
    if not project_id:
        project_id = _get_project_id_with_fallback()

    if not project_id:
        logger.warning(
            "No Project ID detected; Cloud Monitoring MCP toolset will not be available"
        )
        return None

    try:
        logger.info(
            f"Creating Cloud Monitoring MCP toolset for project: {project_id}"
        )

        # Allow override via environment variable
        default_server = "monitoring.googleapis.com-mcp"
        mcp_server = os.environ.get("MONITORING_MCP_SERVER", default_server)
        mcp_server_name = f"projects/{project_id}/locations/global/mcpServers/{mcp_server}"

        # Create ApiRegistry with explicit quota project header
        api_registry = ApiRegistry(
            project_id, header_provider=lambda _: {"x-goog-user-project": project_id}
        )

        # Get the MCP toolset - this creates a new session
        mcp_toolset = api_registry.get_toolset(
            mcp_server_name=mcp_server_name,
            tool_filter=[
                "list_time_series",
                "list_metric_descriptors",
                "list_monitored_resource_descriptors",
            ],
        )

        return mcp_toolset

    except Exception as e:
        logger.error(
            f"Failed to create Cloud Monitoring MCP toolset: {e}", exc_info=True
        )
        return None




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
# This is a single agent (not parallel) that uses BigQuery to analyze at scale
stage0_aggregate_analyzer = aggregate_analyzer
if project_id:
    stage0_aggregate_analyzer.instruction += f"\n\nCurrent Project ID: {project_id}\nUse this for 'projectId' arguments in BigQuery tools."

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

    # Retry loop to handle MCP session timeouts.
    # MCP sessions can terminate during long-running LLM calls (~6+ seconds).
    # When this happens, we create a fresh MCP toolset and retry.
    max_retries = 3
    base_delay = 1.0  # Exponential backoff: 1s, 2s, 4s

    for attempt in range(max_retries):
        try:
            # Create MCP toolset lazily in async context to avoid session lifecycle issues.
            # Creating at module import time causes "Attempted to exit cancel scope in a
            # different task" errors because the session cleanup happens in a different
            # async task than where it was created.
            mcp_toolset = _create_bigquery_mcp_toolset()

            # Create a fresh agent instance with MCP tools for this request.
            # This ensures the MCP session is created in the correct async context.
            tools = list(stage0_aggregate_analyzer.tools)
            if mcp_toolset:
                tools.append(mcp_toolset)

            fresh_analyzer = LlmAgent(
                name=stage0_aggregate_analyzer.name,
                model=stage0_aggregate_analyzer.model,
                description=stage0_aggregate_analyzer.description,
                instruction=stage0_aggregate_analyzer.instruction,
                tools=tools,
            )

            aggregate_tool = AgentTool(fresh_analyzer)

            logger.info(f"Starting aggregate analysis (attempt {attempt + 1}/{max_retries})")

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

        except Exception as e:
            # Check for MCP session errors (Session terminated, connection errors, etc.)
            error_str = str(e)
            is_session_error = (
                "Session terminated" in error_str
                or "session" in error_str.lower() and "error" in error_str.lower()
            )

            if is_session_error and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"MCP session error during attempt {attempt + 1}/{max_retries}: {e}. "
                    f"Retrying in {delay}s with fresh MCP toolset..."
                )
                await asyncio.sleep(delay)
                # Continue to next iteration which creates a new MCP toolset
            else:
                # Not a retryable error or max retries reached
                if attempt >= max_retries - 1:
                    logger.error(
                        f"Aggregate analysis failed after {max_retries} attempts: {e}"
                    )
                raise



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
        args={
            "request": f"Context: {json.dumps(stage1_input)}\nInstruction: Analyze the traces provided."
        },
        tool_context=tool_context,
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
        tool_context=tool_context,
    )


@adk_tool
async def run_logging_query(
    filter_str: str,
    project_id: str | None = None,
    limit: int = 100,
    tool_context: ToolContext = None,
) -> dict:
    """
    Queries Cloud Logging using the remote MCP server.

    This tool uses the Cloud Logging MCP server (logging.googleapis.com/mcp) to
    query log entries. The MCP server URL can be overridden via the LOGGING_MCP_SERVER
    environment variable.

    Args:
        filter_str: Cloud Logging filter string (e.g., 'severity>=ERROR AND resource.type="k8s_container"').
        project_id: The Google Cloud Project ID. If not provided, uses default credentials.
        limit: Maximum number of log entries to return (default 100).
        tool_context: The tool context provided by the ADK.

    Returns:
        Query results from Cloud Logging including matching log entries.

    Example filters:
        - 'severity>=ERROR' - All errors and higher severity
        - 'resource.type="gce_instance"' - Logs from Compute Engine instances
        - 'trace="projects/PROJECT_ID/traces/TRACE_ID"' - Logs correlated with a trace
        - 'timestamp>="2024-01-01T00:00:00Z"' - Time-bounded queries
    """
    if tool_context is None:
        raise ValueError("tool_context is required for running MCP tools")

    if not project_id:
        project_id = _get_project_id_with_fallback()

    if not project_id:
        return {"error": "No project ID available. Set GOOGLE_CLOUD_PROJECT environment variable."}

    max_retries = 3
    base_delay = 1.0

    for attempt in range(max_retries):
        try:
            mcp_toolset = _create_logging_mcp_toolset(project_id)

            if not mcp_toolset:
                # Fallback to direct API client if MCP is unavailable
                logger.warning("Cloud Logging MCP unavailable, falling back to direct API")
                from .tools.o11y_clients import list_log_entries as direct_list_logs
                result = direct_list_logs(project_id, filter_str, limit)
                return {"source": "direct_api", "result": json.loads(result) if isinstance(result, str) else result}

            # Get the tools from the toolset
            tools = await mcp_toolset.get_tools()

            # Find and call list_log_entries
            for tool in tools:
                if tool.name == "list_log_entries":
                    result = await tool.run_async(
                        args={
                            "filter": filter_str,
                            "page_size": limit,
                            "resource_names": [f"projects/{project_id}"],
                        },
                        tool_context=tool_context,
                    )
                    return {"source": "mcp", "result": result}

            return {"error": "list_log_entries tool not found in MCP toolset"}

        except Exception as e:
            error_str = str(e)
            is_session_error = (
                "Session terminated" in error_str
                or "session" in error_str.lower() and "error" in error_str.lower()
            )

            if is_session_error and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"MCP session error during logging query attempt {attempt + 1}/{max_retries}: {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
            else:
                if attempt >= max_retries - 1:
                    logger.error(f"Logging query failed after {max_retries} attempts: {e}")
                raise


@adk_tool
async def run_monitoring_query(
    filter_str: str,
    project_id: str | None = None,
    minutes_ago: int = 60,
    tool_context: ToolContext = None,
) -> dict:
    """
    Queries Cloud Monitoring using the remote MCP server.

    This tool uses the Cloud Monitoring MCP server (monitoring.googleapis.com/mcp) to
    query time series metrics. The MCP server URL can be overridden via the
    MONITORING_MCP_SERVER environment variable.

    Args:
        filter_str: Cloud Monitoring filter string for metrics.
        project_id: The Google Cloud Project ID. If not provided, uses default credentials.
        minutes_ago: How many minutes back to query (default 60).
        tool_context: The tool context provided by the ADK.

    Returns:
        Query results from Cloud Monitoring including time series data.

    Example filters:
        - 'metric.type="compute.googleapis.com/instance/cpu/utilization"' - CPU utilization
        - 'metric.type="loadbalancing.googleapis.com/https/request_count"' - Load balancer requests
        - 'resource.labels.instance_id="12345"' - Filter by instance ID
    """
    if tool_context is None:
        raise ValueError("tool_context is required for running MCP tools")

    if not project_id:
        project_id = _get_project_id_with_fallback()

    if not project_id:
        return {"error": "No project ID available. Set GOOGLE_CLOUD_PROJECT environment variable."}

    max_retries = 3
    base_delay = 1.0
    import time as time_module

    for attempt in range(max_retries):
        try:
            mcp_toolset = _create_monitoring_mcp_toolset(project_id)

            if not mcp_toolset:
                # Fallback to direct API client if MCP is unavailable
                logger.warning("Cloud Monitoring MCP unavailable, falling back to direct API")
                from .tools.o11y_clients import list_time_series as direct_list_metrics
                result = direct_list_metrics(project_id, filter_str, minutes_ago)
                return {"source": "direct_api", "result": json.loads(result) if isinstance(result, str) else result}

            # Get the tools from the toolset
            tools = await mcp_toolset.get_tools()

            # Calculate time interval
            now = time_module.time()
            end_seconds = int(now)
            start_seconds = int(now) - (minutes_ago * 60)

            # Find and call list_time_series
            for tool in tools:
                if tool.name == "list_time_series":
                    result = await tool.run_async(
                        args={
                            "name": f"projects/{project_id}",
                            "filter": filter_str,
                            "interval": {
                                "end_time": {"seconds": end_seconds},
                                "start_time": {"seconds": start_seconds},
                            },
                        },
                        tool_context=tool_context,
                    )
                    return {"source": "mcp", "result": result}

            return {"error": "list_time_series tool not found in MCP toolset"}

        except Exception as e:
            error_str = str(e)
            is_session_error = (
                "Session terminated" in error_str
                or "session" in error_str.lower() and "error" in error_str.lower()
            )

            if is_session_error and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"MCP session error during monitoring query attempt {attempt + 1}/{max_retries}: {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
            else:
                if attempt >= max_retries - 1:
                    logger.error(f"Monitoring query failed after {max_retries} attempts: {e}")
                raise


# Initialize base tools
base_tools = [
    # Three-stage analysis architecture
    run_aggregate_analysis,  # Stage 0: BigQuery aggregate analysis
    run_triage_analysis,  # Stage 1: Trace diff analysis
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
    # GCP MCP tools - Cloud Logging and Cloud Monitoring
    # These use remote MCP servers with fallback to direct API clients
    run_logging_query,  # MCP: logging.googleapis.com/mcp
    run_monitoring_query,  # MCP: monitoring.googleapis.com/mcp
    # Direct API client tools (used as fallback or for simple queries)
    list_log_entries,
    list_time_series,
    list_error_events,
    get_logs_for_trace,
]

# Note: MCP toolsets are NOT created at module level to avoid async context issues.
# Creating MCP sessions at module import time causes "Attempted to exit cancel scope
# in a different task" errors because anyio cancel scopes cannot cross task boundaries.
#
# Instead, MCP toolsets are created lazily within async functions where they are needed.
# This ensures the session is created and managed in the correct async context.
#
# GCP MCP Tools Architecture:
# - BigQuery: run_aggregate_analysis -> _create_bigquery_mcp_toolset() -> google-bigquery.googleapis.com-mcp
# - Logging: run_logging_query -> _create_logging_mcp_toolset() -> logging.googleapis.com-mcp
# - Monitoring: run_monitoring_query -> _create_monitoring_mcp_toolset() -> monitoring.googleapis.com-mcp
# - Trace: Uses direct Cloud Trace API client (no MCP server available)
#
# MCP server URLs can be overridden via environment variables:
# - BIGQUERY_MCP_SERVER (default: google-bigquery.googleapis.com-mcp)
# - LOGGING_MCP_SERVER (default: logging.googleapis.com-mcp)
# - MONITORING_MCP_SERVER (default: monitoring.googleapis.com-mcp)

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
