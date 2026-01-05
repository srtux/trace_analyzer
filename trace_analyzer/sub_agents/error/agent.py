"""Error Analyzer sub-agent for detecting error changes between traces."""

from google.adk.agents import Agent

from ...tools.trace_client import fetch_trace
from ...tools.trace_analysis import extract_errors
from . import prompt

error_analyzer = Agent(
    name="error_analyzer",
    model="gemini-2.5-pro",
    description="Detects and compares errors between traces to identify new failures.",
    instruction=prompt.ERROR_ANALYZER_PROMPT,
    tools=[fetch_trace, extract_errors],
)
