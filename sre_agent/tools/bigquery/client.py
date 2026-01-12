"""BigQuery Client wrapper using MCP."""

import logging
from typing import Any

from google.adk.tools import ToolContext

from ..mcp.gcp import (
    call_mcp_tool_with_retry,
    create_bigquery_mcp_toolset,
    get_project_id_with_fallback,
)

logger = logging.getLogger(__name__)


class BigQueryClient:
    """Wrapper around BigQuery MCP toolset for SQL execution."""

    def __init__(
        self, project_id: str | None = None, tool_context: ToolContext | None = None
    ):
        """Initialize BigQuery Client.

        Args:
            project_id: GCP Project ID.
            tool_context: ADK ToolContext (required for MCP calls).
        """
        self.project_id = project_id or get_project_id_with_fallback()
        self.tool_context = tool_context
        if not self.tool_context:
            raise ValueError("ToolContext is required for BigQueryClient")

    async def execute_query(self, query: str) -> list[dict[str, Any]]:
        """Execute a SQL query using BigQuery MCP.

        Args:
            query: SQL query string.

        Returns:
            List of rows (dicts).
        """
        if not self.project_id:
            logger.error("No project ID for BigQuery execution")
            raise ValueError("No project ID")

        result = await call_mcp_tool_with_retry(
            create_bigquery_mcp_toolset,
            "execute_sql",
            {"sql": query},
            self.tool_context,
            project_id=self.project_id,
        )

        if result.get("status") != "success":
            logger.error(f"BigQuery execution failed: {result.get('error')}")
            raise RuntimeError(f"BigQuery execution failed: {result.get('error')}")

        # MCP 'execute_sql' usually returns a structure like:
        # {"schema": ..., "rows": [...]} or just the rows if simplified.
        # We need to verify the exact output format of the MCP server's execute_sql.
        # Assuming generic MCP generic response which typically puts the data in 'result'.

        # NOTE: The MCP implementation details might vary.
        # If the MCP returns a raw JSON string, we might need to parse it.
        # For now assuming it returns a python dictionary matching the result structure.

        data = result.get("result", {})
        # If 'rows' key exists, return that. fallback to the result itself if it is a list.
        if isinstance(data, dict):
            return data.get("rows", [])
        if isinstance(data, list):
            return data

        return []

    async def get_table_schema(
        self, dataset_id: str, table_id: str
    ) -> list[dict[str, Any]]:
        """Get table schema.

        Args:
            dataset_id: Dataset ID.
            table_id: Table ID.

        Returns:
            List of schema fields.
        """
        if not self.project_id:
            raise ValueError("No project ID")

        result = await call_mcp_tool_with_retry(
            create_bigquery_mcp_toolset,
            "get_table_info",
            {"dataset_id": dataset_id, "table_id": table_id},
            self.tool_context,
            project_id=self.project_id,
        )

        if result.get("status") != "success":
            logger.warning(f"Failed to get table info: {result.get('error')}")
            return []

        # result['result'] should contain 'schema'
        info = result.get("result", {})
        return info.get("schema", {}).get("fields", [])
