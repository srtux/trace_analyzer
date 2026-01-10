"""Cloud Monitoring MCP Integration."""

import logging
import os
import datetime
import time as time_module
from google.adk.tools import ToolContext
from google.adk.tools.api_registry import ApiRegistry
from ..common import adk_tool
from .session import get_project_id_with_fallback

logger = logging.getLogger(__name__)

def create_monitoring_mcp_toolset(project_id: str | None = None):
    """
    Creates a Cloud Monitoring MCP toolset.
    Tools exposed: list_timeseries, query_range
    """
    if not project_id:
        project_id = get_project_id_with_fallback()
    if not project_id:
        logger.warning("No Project ID detected; Cloud Monitoring MCP toolset will not be available")
        return None
    try:
        logger.info(f"Creating Cloud Monitoring MCP toolset for project: {project_id}")
        default_server = "monitoring.googleapis.com-mcp"
        mcp_server = os.environ.get("MONITORING_MCP_SERVER", default_server)
        mcp_server_name = f"projects/{project_id}/locations/global/mcpServers/{mcp_server}"
        
        api_registry = ApiRegistry(
            project_id, header_provider=lambda _: {"x-goog-user-project": project_id}
        )
        return api_registry.get_toolset(
            mcp_server_name=mcp_server_name,
            tool_filter=["list_timeseries", "query_range"],
        )
    except Exception as e:
        logger.error(f"Failed to create Cloud Monitoring MCP toolset: {e}", exc_info=True)
        return None

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
    """
    if tool_context is None:
        raise ValueError("tool_context is required for MCP tools")

    pid = project_id or get_project_id_with_fallback()

    # Build time interval
    if interval_end_time:
        end_dt = datetime.datetime.fromisoformat(interval_end_time.replace("Z", "+00:00"))
        end_seconds = int(end_dt.timestamp())
    else:
        end_seconds = int(time_module.time())

    if interval_start_time:
        start_dt = datetime.datetime.fromisoformat(interval_start_time.replace("Z", "+00:00"))
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

    mcp_toolset = create_monitoring_mcp_toolset(pid)
    if not mcp_toolset:
        return {"error": "Monitoring MCP toolset unavailable"}

    try:
        tools = await mcp_toolset.get_tools()
        for tool in tools:
            if tool.name == "list_timeseries":
                 return await tool.run_async(args=args, tool_context=tool_context)
        return {"error": "Tool not found in MCP"}
    except Exception as e:
        return {"error": str(e)}

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
    """
    if tool_context is None:
        raise ValueError("tool_context is required for MCP tools")

    # Build time range
    if end_time:
        end_str = end_time
    else:
        end_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if start_time:
        start_str = start_time
    else:
        start_ts = time_module.time() - (minutes_ago * 60)
        start_str = datetime.datetime.fromtimestamp(start_ts, tz=datetime.timezone.utc).isoformat()

    args = {
        "query": query,
        "start": start_str,
        "end": end_str,
        "step": step,
    }
    
    pid = project_id or get_project_id_with_fallback()
    mcp_toolset = create_monitoring_mcp_toolset(pid)
    if not mcp_toolset:
        return {"error": "Monitoring MCP toolset unavailable"}

    try:
        tools = await mcp_toolset.get_tools()
        for tool in tools:
             if tool.name == "query_range":
                 return await tool.run_async(args=args, tool_context=tool_context)
        return {"error": "Tool not found in MCP"}
    except Exception as e:
        return {"error": str(e)}
