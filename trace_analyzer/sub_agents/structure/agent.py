"""Structure Analyzer sub-agent for comparing call graph topology between traces."""

from google.adk.agents import Agent

from ...tools.trace_client import fetch_trace
from ...tools.trace_analysis import build_call_graph, find_structural_differences
from . import prompt

structure_analyzer = Agent(
    name="structure_analyzer",
    model="gemini-2.5-pro",
    description="Compares call graph structure between traces to identify behavioral changes.",
    instruction=prompt.STRUCTURE_ANALYZER_PROMPT,
    tools=[fetch_trace, build_call_graph, find_structural_differences],
)
