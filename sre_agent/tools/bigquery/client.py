"""BigQuery Client wrapper using Model Context Protocol (MCP).

This client acts as a bridge to the BigQuery MCP server. Instead of using the
Google Cloud BigQuery client library directly in this process, it delegates
SQL execution and schema inspection to the MCP server.

This architecture allows:
- **Separation of Concerns**: The MCP server handles connection pooling and auth.
- **Sandboxing**: The agent integration is lightweight and stateless.
- **Consistency**: All BigQuery operations go through the same controlled interface.
"""

import logging
from typing import Any, cast

from google.adk.tools import ToolContext  # type: ignore[attr-defined]

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

        assert self.tool_context is not None, "ToolContext required"

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
            return cast(list[dict[str, Any]], data.get("rows", []))
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

        assert self.tool_context is not None, "ToolContext required"

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
        return cast(list[dict[str, Any]], info.get("schema", {}).get("fields", []))
