"""Discovery tool for BigQuery telemetry sources using MCP.

This tool acts as the "Entry Point" for Stage 0 analysis. It intelligently scans
the project's BigQuery datasets to find the standard Cloud Observability export tables:
- `_AllSpans`: For trace data.
- `_AllLogs`: For log data.

It bridges the gap between the agent knowing *what* to query and *where* to query it.
If BigQuery tables are not found, it signals to the agent to fall back to the direct
Trace/Logging APIs (which are slower for aggregate analysis but always available).
"""

import logging
from typing import Any

from google.adk.tools import ToolContext  # type: ignore[attr-defined]

from ..common import adk_tool
from ..mcp.gcp import (
    call_mcp_tool_with_retry,
    create_bigquery_mcp_toolset,
    get_project_id_with_fallback,
)

logger = logging.getLogger(__name__)


@adk_tool
async def discover_telemetry_sources(
    project_id: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Discover BigQuery datasets containing observability data.

    This tool scans the project for datasets that contain standard Cloud Observability
    linked tables: `_AllSpans` (for traces) and `_AllLogs` (for logs).

    Args:
        project_id: GCP project ID. If not provided, uses default credentials.
        tool_context: ADK tool context (required).

    Returns:
        Dictionary containing discovered telemetry sources:
        {
            "trace_table": "project.dataset._AllSpans" | None,
            "log_table": "project.dataset._AllLogs" | None,
            "mode": "bigquery" | "api_fallback",
            "datasets_scanned": ["dataset1", "dataset2"]
        }
    """
    logger.info("ENTER discover_telemetry_sources")
    if tool_context is None:
        raise ValueError("tool_context is required for MCP tools")

    pid = project_id or get_project_id_with_fallback()
    if not pid:
        return {
            "trace_table": None,
            "log_table": None,
            "mode": "api_fallback",
            "error": "No project ID detected",
        }

    # 1. List Datasets
    logger.info(f"Calling list_dataset_ids for project {pid}")
    list_datasets_result = await call_mcp_tool_with_retry(
        create_bigquery_mcp_toolset,
        "list_dataset_ids",
        {"project_id": pid},
        tool_context,
        project_id=pid,
    )
    logger.info(f"list_dataset_ids result: {list_datasets_result}")

    if list_datasets_result.get("status") != "success":
        error_msg = list_datasets_result.get("error", "Unknown error")
        error_type = list_datasets_result.get("error_type", "UNKNOWN")
        is_non_retryable = list_datasets_result.get("non_retryable", False)

        logger.warning(f"Failed to list datasets: {error_msg} (type={error_type})")

        # Provide actionable guidance based on the fallback
        return {
            "trace_table": None,
            "log_table": None,
            "mode": "api_fallback",
            "warning": (
                f"BigQuery discovery failed - switching to direct API mode. "
                f"Error: {error_msg}. "
                "NEXT STEPS: Use direct API tools instead of BigQuery: "
                "- For traces: use fetch_trace or list_traces "
                "- For logs: use list_log_entries "
                "- For metrics: use query_promql or list_time_series. "
                "DO NOT call discover_telemetry_sources again."
            ),
            "error_type": error_type,
            "non_retryable": is_non_retryable,
        }

    datasets = list_datasets_result.get("result", [])
    if isinstance(datasets, dict):
        # Handle wrapped response (common in MCP)
        # Try common keys like 'datasets', 'ids', or 'names'
        datasets = (
            datasets.get("datasets")
            or datasets.get("ids")
            or datasets.get("names")
            or []
        )

    if not isinstance(datasets, list):
        # Handle potential string or other unexpected formats
        logger.warning(f"Unexpected dataset format: {type(datasets)} - {datasets}")
        datasets = []

    trace_table = None
    log_table = None
    scanned_datasets = []

    # 2. Scan each dataset for tables
    # IMPACT: Limiting to first 5 datasets to prevent execution timeout during discovery
    for dataset_id in datasets[:5]:
        scanned_datasets.append(dataset_id)

        # Optimization: Stop if both found
        if trace_table and log_table:
            break

        logger.info(f"Scanning dataset: {dataset_id}")
        list_tables_result = await call_mcp_tool_with_retry(
            create_bigquery_mcp_toolset,
            "list_table_ids",
            {"dataset_id": dataset_id, "project_id": pid},
            tool_context,
            project_id=pid,
        )

        if list_tables_result.get("status") != "success":
            logger.warning(
                f"Failed to list tables for {dataset_id}: {list_tables_result.get('error')}"
            )
            continue

        tables = list_tables_result.get("result", [])
        if not isinstance(tables, list):
            continue

        # Check for target tables
        if "_AllSpans" in tables:
            trace_table = f"{pid}.{dataset_id}._AllSpans"
            logger.info(f"Found trace table: {trace_table}")

        if "_AllLogs" in tables:
            log_table = f"{pid}.{dataset_id}._AllLogs"
            logger.info(f"Found log table: {log_table}")

    mode = "bigquery" if (trace_table or log_table) else "api_fallback"

    result = {
        "trace_table": trace_table,
        "log_table": log_table,
        "mode": mode,
        "datasets_scanned": scanned_datasets,
        "project_id": pid,
    }
    logger.info(f"EXIT discover_telemetry_sources with {result}")
    return result
