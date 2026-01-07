"""Service Impact Analyzer sub-agent for assessing service-level impact."""

from google.adk.agents import Agent

from ...tools.trace_client import fetch_trace, list_traces
from ...tools.trace_analysis import extract_errors
from ...tools.statistical_analysis import compute_service_level_stats
from . import prompt

service_impact_analyzer = Agent(
    name="service_impact_analyzer",
    model="gemini-2.5-pro",
    description="Analyzes which services are impacted by trace anomalies and assesses blast radius.",
    instruction=prompt.SERVICE_IMPACT_ANALYZER_PROMPT,
    tools=[
        fetch_trace,
        list_traces,
        compute_service_level_stats,
        extract_errors,
    ],
)
