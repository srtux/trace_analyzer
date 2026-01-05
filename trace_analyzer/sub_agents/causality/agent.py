"""Causality Analyzer sub-agent for root cause analysis."""

from google.adk.agents import Agent

from ...tools.trace_client import fetch_trace
from ...tools.trace_analysis import find_structural_differences
from ...tools.statistical_analysis import perform_causal_analysis, analyze_critical_path
from . import prompt

causality_analyzer = Agent(
    name="causality_analyzer",
    model="gemini-2.5-pro",
    description="Performs root cause analysis to identify the origin of performance issues and trace their propagation.",
    instruction=prompt.CAUSALITY_ANALYZER_PROMPT,
    tools=[
        fetch_trace,
        perform_causal_analysis,
        analyze_critical_path,
        find_structural_differences,
    ],
)
