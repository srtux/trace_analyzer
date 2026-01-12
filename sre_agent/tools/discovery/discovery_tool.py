"""Discovery tool for BigQuery telemetry sources using MCP."""

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
    list_datasets_result = await call_mcp_tool_with_retry(
        create_bigquery_mcp_toolset,
        "list_dataset_ids",
        {},
        tool_context,
        project_id=pid,
    )

    if list_datasets_result.get("status") != "success":
        logger.warning(f"Failed to list datasets: {list_datasets_result.get('error')}")
        return {
            "trace_table": None,
            "log_table": None,
            "mode": "api_fallback",
            "error": f"Failed to list datasets: {list_datasets_result.get('error')}",
        }

    datasets = list_datasets_result.get("result", [])
    if not isinstance(datasets, list):
        # Handle potential string or wrapped response (MCP outputs vary)
        # Assuming list of strings for now based on typical MCP behavior
        logger.warning(f"Unexpected dataset format: {type(datasets)}")
        datasets = []

    trace_table = None
    log_table = None
    scanned_datasets = []

    # 2. Scan each dataset for tables
    for dataset_id in datasets:
        scanned_datasets.append(dataset_id)

        # Optimization: Stop if both found
        if trace_table and log_table:
            break

        list_tables_result = await call_mcp_tool_with_retry(
            create_bigquery_mcp_toolset,
            "list_table_ids",
            {"dataset_id": dataset_id},
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

        if "_AllLogs" in tables:
            log_table = f"{pid}.{dataset_id}._AllLogs"

    mode = "bigquery" if (trace_table or log_table) else "api_fallback"

    return {
        "trace_table": trace_table,
        "log_table": log_table,
        "mode": mode,
        "datasets_scanned": scanned_datasets,
        "project_id": pid,
    }
