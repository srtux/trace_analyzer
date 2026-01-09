"""Cloud Trace Analyzer - Root Agent Definition.

This module implements a three-stage hierarchical analysis architecture for
trace analysis, plus generic GCP observability tools.

Stage 0 (Aggregate Analysis):
    - aggregate_analyzer: BigQuery-powered analysis of trace data at scale

Stage 1 (Triage Squad):
    - latency_analyzer, error_analyzer, structure_analyzer, statistics_analyzer

Stage 2 (Deep Dive Squad):
    - causality_analyzer, service_impact_analyzer

GCP MCP Tools (Generic - usable for any purpose):
    These tools provide direct access to GCP observability services via MCP:

    BigQuery:
        - execute_sql, list_dataset_ids, list_table_ids, get_table_info
        - Server: google-bigquery.googleapis.com-mcp (override: BIGQUERY_MCP_SERVER)

    Cloud Logging:
        - list_log_entries: Search and retrieve log entries
        - Server: logging.googleapis.com-mcp (override: LOGGING_MCP_SERVER)

    Cloud Monitoring:
        - list_timeseries: Query time series metrics data
        - query_range: Evaluate PromQL queries over a time range
        - Server: monitoring.googleapis.com-mcp (override: MONITORING_MCP_SERVER)

    Cloud Trace:
        - Uses direct API client (fetch_trace, list_traces, etc.)
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
    Creates a Cloud Logging MCP toolset with generic logging capabilities.

    This toolset provides access to Cloud Logging for any use case - debugging,
    auditing, monitoring, or analysis. Not limited to trace analysis.

    Tools exposed:
        - list_log_entries: Search and retrieve log entries. Essential for debugging
          application behavior, finding error messages, or auditing events.

    Environment variable override:
        LOGGING_MCP_SERVER: Override the default MCP server (default: logging.googleapis.com-mcp)

    NOTE: Must be called in an async context for proper MCP session lifecycle.
    """
    if not project_id:
        project_id = _get_project_id_with_fallback()

    if not project_id:
        logger.warning(
            "No Project ID detected; Cloud Logging MCP toolset will not be available"
        )
        return None

    try:
        logger.info(f"Creating Cloud Logging MCP toolset for project: {project_id}")

        default_server = "logging.googleapis.com-mcp"
        mcp_server = os.environ.get("LOGGING_MCP_SERVER", default_server)
        mcp_server_name = f"projects/{project_id}/locations/global/mcpServers/{mcp_server}"

        api_registry = ApiRegistry(
            project_id, header_provider=lambda _: {"x-goog-user-project": project_id}
        )

        # Expose list_log_entries as the primary tool for log queries
        mcp_toolset = api_registry.get_toolset(
            mcp_server_name=mcp_server_name,
            tool_filter=["list_log_entries"],
        )

        return mcp_toolset

    except Exception as e:
        logger.error(f"Failed to create Cloud Logging MCP toolset: {e}", exc_info=True)
        return None


def _create_monitoring_mcp_toolset(project_id: str | None = None):
    """
    Creates a Cloud Monitoring MCP toolset with generic metrics capabilities.

    This toolset provides access to Cloud Monitoring for any use case - performance
    monitoring, alerting, capacity planning, or analysis. Not limited to trace analysis.

    Tools exposed:
        - list_timeseries: Query time series metrics data from Cloud Monitoring API.
          Use for retrieving metric values over time.
        - query_range: Evaluate PromQL queries over a time range. Useful for
          complex metric aggregations and calculations.

    Environment variable override:
        MONITORING_MCP_SERVER: Override the default MCP server (default: monitoring.googleapis.com-mcp)

    NOTE: Must be called in an async context for proper MCP session lifecycle.
    """
    if not project_id:
        project_id = _get_project_id_with_fallback()

    if not project_id:
        logger.warning(
            "No Project ID detected; Cloud Monitoring MCP toolset will not be available"
        )
        return None

    try:
        logger.info(f"Creating Cloud Monitoring MCP toolset for project: {project_id}")

        default_server = "monitoring.googleapis.com-mcp"
        mcp_server = os.environ.get("MONITORING_MCP_SERVER", default_server)
        mcp_server_name = f"projects/{project_id}/locations/global/mcpServers/{mcp_server}"

        api_registry = ApiRegistry(
            project_id, header_provider=lambda _: {"x-goog-user-project": project_id}
        )

        # Expose list_timeseries and query_range for metrics queries
        mcp_toolset = api_registry.get_toolset(
            mcp_server_name=mcp_server_name,
            tool_filter=["list_timeseries", "query_range"],
        )

        return mcp_toolset

    except Exception as e:
        logger.error(f"Failed to create Cloud Monitoring MCP toolset: {e}", exc_info=True)
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


# =============================================================================
# Generic GCP MCP Tools
# =============================================================================
# These tools provide direct access to GCP observability services via MCP.
# They are generic and can be used for any purpose, not just trace analysis.
# Custom analysis logic should be implemented in subagents, not here.


async def _call_mcp_tool_with_retry(
    create_toolset_fn,
    tool_name: str,
    args: dict,
    tool_context: ToolContext,
    project_id: str | None = None,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> dict:
    """
    Generic helper to call an MCP tool with retry logic for session errors.

    Args:
        create_toolset_fn: Function to create the MCP toolset.
        tool_name: Name of the MCP tool to call.
        args: Arguments to pass to the tool.
        tool_context: ADK tool context.
        project_id: Optional project ID override.
        max_retries: Max retry attempts for session errors.
        base_delay: Base delay for exponential backoff.

    Returns:
        Tool result or error dict.
    """
    if not project_id:
        project_id = _get_project_id_with_fallback()

    if not project_id:
        return {"error": "No project ID available. Set GOOGLE_CLOUD_PROJECT environment variable."}

    for attempt in range(max_retries):
        try:
            mcp_toolset = create_toolset_fn(project_id)

            if not mcp_toolset:
                return {"error": f"MCP toolset unavailable for {tool_name}"}

            tools = await mcp_toolset.get_tools()

            for tool in tools:
                if tool.name == tool_name:
                    result = await tool.run_async(args=args, tool_context=tool_context)
                    return {"source": "mcp", "result": result}

            return {"error": f"{tool_name} tool not found in MCP toolset"}

        except Exception as e:
            error_str = str(e)
            is_session_error = (
                "Session terminated" in error_str
                or "session" in error_str.lower() and "error" in error_str.lower()
            )

            if is_session_error and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"MCP session error during {tool_name} attempt {attempt + 1}/{max_retries}: {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
            else:
                if attempt >= max_retries - 1:
                    logger.error(f"{tool_name} failed after {max_retries} attempts: {e}")
                raise


@adk_tool
async def mcp_list_log_entries(
    filter: str,
    project_id: str | None = None,
    page_size: int = 100,
    order_by: str | None = None,
    tool_context: ToolContext = None,
) -> dict:
    """
    Search and retrieve log entries from Google Cloud Logging via MCP.

    This is the primary tool for querying Cloud Logging. Use it for debugging
    application behavior, finding specific error messages, auditing events,
    or any log analysis task.

    Args:
        filter: Cloud Logging filter expression. Powerful syntax for selecting logs
            by severity, resource type, text content, labels, and more.
        project_id: GCP project ID. If not provided, uses default credentials.
        page_size: Maximum number of log entries to return (default 100).
        order_by: Optional field to sort by (e.g., "timestamp desc").
        tool_context: ADK tool context (required).

    Returns:
        Log entries matching the filter criteria.

    Example filters:
        - 'severity>=ERROR' - All errors and above
        - 'resource.type="k8s_container"' - Kubernetes container logs
        - 'resource.type="gce_instance"' - Compute Engine logs
        - 'textPayload:"OutOfMemory"' - Logs containing specific text
        - 'jsonPayload.level="error"' - Structured logs by field
        - 'trace="projects/PROJECT/traces/TRACE_ID"' - Logs for a trace
        - 'timestamp>="2024-01-01T00:00:00Z"' - Time-bounded queries
        - 'labels.env="production" AND severity>=WARNING' - Combined filters
    """
    if tool_context is None:
        raise ValueError("tool_context is required for MCP tools")

    args = {
        "filter": filter,
        "page_size": page_size,
    }
    if order_by:
        args["order_by"] = order_by

    # Add resource_names if project_id is available
    pid = project_id or _get_project_id_with_fallback()
    if pid:
        args["resource_names"] = [f"projects/{pid}"]

    return await _call_mcp_tool_with_retry(
        _create_logging_mcp_toolset,
        "list_log_entries",
        args,
        tool_context,
        project_id=project_id,
    )


@adk_tool
async def mcp_list_timeseries(
    filter: str,
    project_id: str | None = None,
    interval_start_time: str | None = None,
    interval_end_time: str | None = None,
    minutes_ago: int = 60,
    aggregation: dict | None = None,
    tool_context: ToolContext = None,
) -> dict:
    """
    Query time series metrics data from Google Cloud Monitoring via MCP.

    Use this tool to retrieve metric values over time for monitoring, alerting,
    capacity planning, performance analysis, or any metrics-based task.

    Args:
        filter: Monitoring filter string for selecting metrics and resources.
        project_id: GCP project ID. If not provided, uses default credentials.
        interval_start_time: Start of time interval (ISO format). If not provided,
            calculated from minutes_ago.
        interval_end_time: End of time interval (ISO format). If not provided,
            uses current time.
        minutes_ago: Minutes back from now for start time (default 60). Only used
            if interval_start_time is not provided.
        aggregation: Optional aggregation settings (alignment_period, per_series_aligner, etc.)
        tool_context: ADK tool context (required).

    Returns:
        Time series data with metric values, labels, and timestamps.

    Example filters:
        - 'metric.type="compute.googleapis.com/instance/cpu/utilization"' - CPU usage
        - 'metric.type="loadbalancing.googleapis.com/https/request_count"' - LB requests
        - 'metric.type="cloudsql.googleapis.com/database/cpu/utilization"' - Cloud SQL CPU
        - 'resource.labels.instance_id="12345"' - Filter by instance
        - 'metric.labels.response_code="500"' - Filter by metric label
    """
    if tool_context is None:
        raise ValueError("tool_context is required for MCP tools")

    import time as time_module
    from datetime import datetime, timezone

    pid = project_id or _get_project_id_with_fallback()

    # Build time interval
    if interval_end_time:
        end_dt = datetime.fromisoformat(interval_end_time.replace("Z", "+00:00"))
        end_seconds = int(end_dt.timestamp())
    else:
        end_seconds = int(time_module.time())

    if interval_start_time:
        start_dt = datetime.fromisoformat(interval_start_time.replace("Z", "+00:00"))
        start_seconds = int(start_dt.timestamp())
    else:
        start_seconds = end_seconds - (minutes_ago * 60)

    args = {
        "name": f"projects/{pid}" if pid else "",
        "filter": filter,
        "interval": {
            "end_time": {"seconds": end_seconds},
            "start_time": {"seconds": start_seconds},
        },
    }

    if aggregation:
        args["aggregation"] = aggregation

    return await _call_mcp_tool_with_retry(
        _create_monitoring_mcp_toolset,
        "list_timeseries",
        args,
        tool_context,
        project_id=project_id,
    )


@adk_tool
async def mcp_query_range(
    query: str,
    project_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    minutes_ago: int = 60,
    step: str = "60s",
    tool_context: ToolContext = None,
) -> dict:
    """
    Evaluate a PromQL query over a time range via Cloud Monitoring MCP.

    Use this for complex metric aggregations, calculations, and analysis using
    PromQL syntax. Ideal for rate calculations, histogram analysis, and
    multi-metric correlations.

    Args:
        query: PromQL query expression.
        project_id: GCP project ID. If not provided, uses default credentials.
        start_time: Start of query range (ISO format or RFC3339).
        end_time: End of query range (ISO format or RFC3339).
        minutes_ago: Minutes back from now for start time (default 60).
        step: Query resolution step (default "60s").
        tool_context: ADK tool context (required).

    Returns:
        Query results with time series data.

    Example queries:
        - 'rate(http_requests_total[5m])' - Request rate over 5 minutes
        - 'sum by (status_code)(http_requests_total)' - Requests grouped by status
        - 'histogram_quantile(0.95, http_request_duration_bucket)' - P95 latency
        - 'increase(errors_total[1h])' - Error count increase over 1 hour
    """
    if tool_context is None:
        raise ValueError("tool_context is required for MCP tools")

    import time as time_module
    from datetime import datetime, timezone

    # Build time range
    if end_time:
        end_str = end_time
    else:
        end_str = datetime.now(timezone.utc).isoformat()

    if start_time:
        start_str = start_time
    else:
        start_ts = time_module.time() - (minutes_ago * 60)
        start_str = datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat()

    args = {
        "query": query,
        "start": start_str,
        "end": end_str,
        "step": step,
    }

    return await _call_mcp_tool_with_retry(
        _create_monitoring_mcp_toolset,
        "query_range",
        args,
        tool_context,
        project_id=project_id,
    )


# Initialize base tools
base_tools = [
    # ==========================================================================
    # GCP MCP Tools (Generic - usable for any purpose)
    # ==========================================================================
    # These tools provide direct access to GCP observability services via MCP.
    # They are generic and can be used for debugging, monitoring, analysis, etc.
    #
    # Cloud Logging MCP (logging.googleapis.com/mcp)
    mcp_list_log_entries,  # Primary tool for log queries
    #
    # Cloud Monitoring MCP (monitoring.googleapis.com/mcp)
    mcp_list_timeseries,  # Query time series metrics
    mcp_query_range,  # PromQL queries over time range
    #
    # ==========================================================================
    # Trace Analysis Tools (Subagent-based architecture)
    # ==========================================================================
    # Three-stage analysis: Aggregate → Triage → Deep Dive
    run_aggregate_analysis,  # Stage 0: BigQuery aggregate analysis
    run_triage_analysis,  # Stage 1: Trace diff analysis
    run_deep_dive_analysis,  # Stage 2: Root cause analysis
    #
    # BigQuery-powered OpenTelemetry analysis (query builders for subagents)
    analyze_aggregate_metrics,
    find_exemplar_traces,
    compare_time_periods,
    detect_trend_changes,
    correlate_logs_with_trace,
    #
    # Trace selection helpers
    select_traces_from_error_reports,
    select_traces_from_monitoring_alerts,
    select_traces_from_statistical_outliers,
    select_traces_manually,
    #
    # ==========================================================================
    # Cloud Trace Tools (Direct API - no MCP server available)
    # ==========================================================================
    find_example_traces,
    fetch_trace,
    list_traces,
    get_trace_by_url,
    summarize_trace,
    validate_trace_quality,
    analyze_trace_patterns,
    get_current_time,
    #
    # ==========================================================================
    # Direct API Fallback Tools
    # ==========================================================================
    # These use direct GCP client libraries. Useful when MCP is unavailable
    # or for simple queries that don't need MCP features.
    list_log_entries,  # Direct Cloud Logging API
    list_time_series,  # Direct Cloud Monitoring API
    list_error_events,
    get_logs_for_trace,
]

# =============================================================================
# MCP Architecture Notes
# =============================================================================
# MCP toolsets are created lazily in async context to avoid session lifecycle
# issues. Creating at module import causes "Attempted to exit cancel scope in a
# different task" errors.
#
# GCP MCP Tools:
#   - BigQuery: _create_bigquery_mcp_toolset() → google-bigquery.googleapis.com-mcp
#   - Logging: _create_logging_mcp_toolset() → logging.googleapis.com-mcp
#   - Monitoring: _create_monitoring_mcp_toolset() → monitoring.googleapis.com-mcp
#   - Trace: Direct API client (no MCP server)
#
# Override MCP servers via environment variables:
#   - BIGQUERY_MCP_SERVER (default: google-bigquery.googleapis.com-mcp)
#   - LOGGING_MCP_SERVER (default: logging.googleapis.com-mcp)
#   - MONITORING_MCP_SERVER (default: monitoring.googleapis.com-mcp)

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
