"""BigQuery MCP Integration."""

import logging
import os
from google.adk.tools import ToolContext
from google.adk.tools.api_registry import ApiRegistry
from .session import get_project_id_with_fallback

logger = logging.getLogger(__name__)

def create_bigquery_mcp_toolset(project_id: str | None = None):
    """
    Creates a new instance of the BigQuery MCP toolset.
    Tools exposed: execute_sql, list_dataset_ids, etc.
    """
    if not project_id:
        project_id = get_project_id_with_fallback()
    if not project_id:
        logger.warning("No Project ID detected; BigQuery MCP toolset will not be available")
        return None
    try:
        logger.info(f"Creating BigQuery MCP toolset for project: {project_id}")
        default_server = "google-bigquery.googleapis.com-mcp"
        mcp_server = os.environ.get("BIGQUERY_MCP_SERVER", default_server)
        mcp_server_name = f"projects/{project_id}/locations/global/mcpServers/{mcp_server}"
        
        api_registry = ApiRegistry(
            project_id, header_provider=lambda _: {"x-goog-user-project": project_id}
        )
        return api_registry.get_toolset(
            mcp_server_name=mcp_server_name,
            tool_filter=[
                "execute_sql",
                "list_dataset_ids",
                "list_table_ids",
                "get_table_info",
            ],
        )
    except Exception as e:
        logger.error(f"Failed to create BigQuery MCP toolset: {e}", exc_info=True)
        return None
