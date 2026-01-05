"""Latency Analyzer sub-agent for comparing span timings between traces."""

from google.adk.agents import Agent

from ...tools.trace_client import fetch_trace
from ...tools.trace_analysis import calculate_span_durations, compare_span_timings
from . import prompt

latency_analyzer = Agent(
    name="latency_analyzer",
    model="gemini-2.5-pro",
    description="Analyzes and compares span latencies between traces to identify slowdowns.",
    instruction=prompt.LATENCY_ANALYZER_PROMPT,
    tools=[fetch_trace, calculate_span_durations, compare_span_timings],
)
