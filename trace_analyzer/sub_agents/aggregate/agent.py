"""Aggregate Analyzer - Analyzes trace data at scale using BigQuery."""

from google.adk.agents import LlmAgent

from .prompt import AGGREGATE_ANALYZER_PROMPT
from ...tools.bigquery_otel import (
    analyze_aggregate_metrics,
    compare_time_periods,
    correlate_logs_with_trace,
    detect_trend_changes,
    find_exemplar_traces,
)

aggregate_analyzer = LlmAgent(
    name="aggregate_analyzer",
    model="gemini-2.0-flash-001",
    description=(
        "Analyzes trace data at scale using BigQuery to identify trends, patterns, "
        "and select exemplar traces for investigation. Uses OpenTelemetry schema."
    ),
    instruction=AGGREGATE_ANALYZER_PROMPT,
    tools=[
        analyze_aggregate_metrics,
        find_exemplar_traces,
        compare_time_periods,
        detect_trend_changes,
        correlate_logs_with_trace,
    ],
)
