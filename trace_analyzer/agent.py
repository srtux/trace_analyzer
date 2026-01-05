"""Cloud Trace Analyzer - Root Agent Definition."""

from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool

from . import prompt
from .tools.trace_client import find_example_traces, fetch_trace, list_traces, get_trace_by_url
from .sub_agents.latency.agent import latency_analyzer
from .sub_agents.error.agent import error_analyzer
from .sub_agents.structure.agent import structure_analyzer
from .sub_agents.statistics.agent import statistics_analyzer
from .sub_agents.causality.agent import causality_analyzer

trace_analyzer_agent = LlmAgent(
    name="trace_analyzer_agent",
    model="gemini-2.5-pro",  # Using 2.5-pro for better reasoning capabilities
    description="Orchestrates a team of trace analysis specialists to perform diff analysis between distributed traces.",
    instruction=prompt.ROOT_AGENT_PROMPT,
    output_key="trace_analysis_report",
    tools=[
        # Direct tools for trace discovery and fetching
        find_example_traces,
        fetch_trace,
        list_traces,
        get_trace_by_url,
        # Sub-agents for specialized analysis
        AgentTool(agent=latency_analyzer),
        AgentTool(agent=error_analyzer),
        AgentTool(agent=structure_analyzer),
        AgentTool(agent=statistics_analyzer),
        AgentTool(agent=causality_analyzer),
    ],
)

# Expose as root_agent for ADK CLI compatibility
root_agent = trace_analyzer_agent

