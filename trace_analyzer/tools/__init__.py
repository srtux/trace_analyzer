"""Tools for the Cloud Trace Analyzer agent."""

from .statistical_analysis import (
    analyze_critical_path,
    compute_latency_statistics,
    compute_service_level_stats,
    detect_latency_anomalies,
    perform_causal_analysis,
)
from .trace_analysis import (
    build_call_graph,
    calculate_span_durations,
    compare_span_timings,
    extract_errors,
    find_structural_differences,
)
from .o11y_clients import (
    fetch_trace,
    find_example_traces,
    get_trace_by_url,
    list_traces,
)

__all__ = [
    "analyze_critical_path",
    "build_call_graph",
    # Basic analysis tools
    "calculate_span_durations",
    "compare_span_timings",
    # Statistical analysis tools
    "compute_latency_statistics",
    "compute_service_level_stats",
    "detect_latency_anomalies",
    "extract_errors",
    # Trace client tools
    "fetch_trace",
    "find_example_traces",
    "find_structural_differences",
    "get_trace_by_url",
    "list_traces",
    "perform_causal_analysis",
]
