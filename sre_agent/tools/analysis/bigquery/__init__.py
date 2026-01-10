"""BigQuery tools for SRE Agent.

This module provides BigQuery-powered analysis tools, particularly for
OpenTelemetry trace and log data exported to BigQuery.

Tools:
    - analyze_aggregate_metrics: Aggregate metrics analysis
    - find_exemplar_traces: Find representative traces
    - compare_time_periods: Compare before/after metrics
    - detect_trend_changes: Time series trend analysis
    - correlate_logs_with_trace: Log correlation for root cause
"""

from .otel import (
    analyze_aggregate_metrics,
    compare_time_periods,
    correlate_logs_with_trace,
    detect_trend_changes,
    find_exemplar_traces,
)

__all__ = [
    "analyze_aggregate_metrics",
    "compare_time_periods",
    "correlate_logs_with_trace",
    "detect_trend_changes",
    "find_exemplar_traces",
]
