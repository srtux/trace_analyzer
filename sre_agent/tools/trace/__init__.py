"""Trace analysis tools for SRE Agent.

This module provides tools for distributed trace analysis:
- Cloud Trace API clients for fetching and listing traces
- Trace analysis utilities (durations, errors, call graphs)
- Trace comparison tools for diff analysis
- Trace filter utilities for building query strings

Tools:
    Trace API:
        - fetch_trace: Fetch a specific trace by ID
        - list_traces: List traces with filtering
        - find_example_traces: Discover representative traces
        - get_trace_by_url: Parse Cloud Console URLs

    Analysis:
        - calculate_span_durations: Extract timing information
        - extract_errors: Find error spans
        - build_call_graph: Build hierarchical call graph
        - summarize_trace: Create trace summary
        - validate_trace_quality: Check trace data quality

    Comparison:
        - compare_span_timings: Compare timings between traces
        - find_structural_differences: Compare call graph structures

    Filters:
        - TraceQueryBuilder: Build Cloud Trace filter strings
        - build_trace_filter: Convenience filter builder
        - select_traces_from_*: Trace selection strategies
"""

from .clients import (
    fetch_trace,
    fetch_trace_data,
    list_traces,
    find_example_traces,
    get_trace_by_url,
    get_current_time,
    validate_trace,
)
from .analysis import (
    calculate_span_durations,
    extract_errors,
    build_call_graph,
    summarize_trace,
    validate_trace_quality,
)
from .comparison import (
    compare_span_timings,
    find_structural_differences,
)
from .filters import (
    TraceQueryBuilder,
    TraceSelector,
    build_trace_filter,
    select_traces_from_error_reports,
    select_traces_from_monitoring_alerts,
    select_traces_from_statistical_outliers,
    select_traces_manually,
)

__all__ = [
    # API clients
    "fetch_trace",
    "fetch_trace_data",
    "list_traces",
    "find_example_traces",
    "get_trace_by_url",
    "get_current_time",
    "validate_trace",
    # Analysis
    "calculate_span_durations",
    "extract_errors",
    "build_call_graph",
    "summarize_trace",
    "validate_trace_quality",
    # Comparison
    "compare_span_timings",
    "find_structural_differences",
    # Filters
    "TraceQueryBuilder",
    "TraceSelector",
    "build_trace_filter",
    "select_traces_from_error_reports",
    "select_traces_from_monitoring_alerts",
    "select_traces_from_statistical_outliers",
    "select_traces_manually",
]
