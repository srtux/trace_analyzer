"""Tools for the Cloud Trace Analyzer agent."""

from .trace_client import (
    fetch_trace,
    list_traces,
    find_example_traces,
    get_trace_by_url,
)
from .trace_analysis import (
    calculate_span_durations,
    extract_errors,
    build_call_graph,
    compare_span_timings,
    find_structural_differences,
)
from .statistical_analysis import (
    compute_latency_statistics,
    detect_latency_anomalies,
    analyze_critical_path,
    perform_causal_analysis,
    compute_service_level_stats,
)

__all__ = [
    # Trace client tools
    "fetch_trace",
    "list_traces",
    "find_example_traces",
    "get_trace_by_url",
    # Basic analysis tools
    "calculate_span_durations",
    "extract_errors",
    "build_call_graph",
    "compare_span_timings",
    "find_structural_differences",
    # Statistical analysis tools
    "compute_latency_statistics",
    "detect_latency_anomalies",
    "analyze_critical_path",
    "perform_causal_analysis",
    "compute_service_level_stats",
]
