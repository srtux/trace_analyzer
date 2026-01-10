"""SRE Agent - Google Cloud Observability Analysis Agent.

An ADK-based agent for analyzing telemetry data from Google Cloud Observability:
traces, logs, and metrics. Specializes in distributed trace analysis with
multi-stage investigation.

Usage:
    from sre_agent import root_agent

    # Or with MCP tools
    from sre_agent.agent import get_agent_with_mcp_tools
    agent = await get_agent_with_mcp_tools()
"""

from .agent import root_agent, sre_agent
from . import tools

__all__ = ["root_agent", "sre_agent", "tools"]
