"""Statistics Analyzer sub-agent for statistical analysis of trace data."""

from google.adk.agents import Agent

from ...tools.statistical_analysis import (
    analyze_critical_path,
    compute_latency_statistics,
    compute_service_level_stats,
    detect_latency_anomalies,
)
from ...tools.o11y_clients import fetch_trace, list_traces
from . import prompt

statistics_analyzer = Agent(
    name="statistics_analyzer",
    model="gemini-2.5-pro",
    description="Performs statistical analysis on trace data including percentiles, anomaly detection, and critical path analysis.",
    instruction=prompt.STATISTICS_ANALYZER_PROMPT,
    tools=[
        fetch_trace,
        list_traces,
        compute_latency_statistics,
        detect_latency_anomalies,
        analyze_critical_path,
        compute_service_level_stats,
    ],
)
