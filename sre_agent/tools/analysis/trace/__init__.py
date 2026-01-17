"""Trace analysis tools for SRE Agent."""

from .analysis import (
    build_call_graph,
    calculate_span_durations,
    extract_errors,
    summarize_trace,
    validate_trace_quality,
)
from .comparison import (
    compare_span_timings,
    find_structural_differences,
)
from .filters import (
    select_traces_from_statistical_outliers,
    select_traces_manually,
)
from .patterns import (
    detect_all_sre_patterns,
    detect_cascading_timeout,
    detect_connection_pool_issues,
    detect_retry_storm,
)
from .statistical_analysis import (
    analyze_trace_patterns,
    compute_latency_statistics,
    detect_latency_anomalies,
    perform_causal_analysis,
)

__all__ = [
    "analyze_trace_patterns",
    "build_call_graph",
    "calculate_span_durations",
    "compare_span_timings",
    "compute_latency_statistics",
    "detect_all_sre_patterns",
    "detect_cascading_timeout",
    "detect_connection_pool_issues",
    "detect_latency_anomalies",
    "detect_retry_storm",
    "extract_errors",
    "find_structural_differences",
    "perform_causal_analysis",
    "select_traces_from_statistical_outliers",
    "select_traces_manually",
    "summarize_trace",
    "validate_trace_quality",
]
