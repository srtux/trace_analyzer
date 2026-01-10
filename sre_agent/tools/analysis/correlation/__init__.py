"""Cross-signal correlation tools for advanced SRE debugging.

This module provides tools for correlating data across traces, logs, and metrics
to enable comprehensive observability analysis using OpenTelemetry signals.

Key capabilities:
- Trace-Metrics correlation using exemplars
- Trace-Logs correlation using trace context
- Multi-signal timeline alignment
- Critical path analysis
- Service dependency mapping
"""

from .critical_path import (
    analyze_critical_path,
    calculate_critical_path_contribution,
    find_bottleneck_services,
)
from .cross_signal import (
    analyze_signal_correlation_strength,
    build_cross_signal_timeline,
    correlate_metrics_with_traces_via_exemplars,
    correlate_trace_with_metrics,
)
from .dependencies import (
    analyze_upstream_downstream_impact,
    build_service_dependency_graph,
    detect_circular_dependencies,
)

__all__ = [
    # Critical path analysis
    "analyze_critical_path",
    "analyze_signal_correlation_strength",
    "analyze_upstream_downstream_impact",
    "build_cross_signal_timeline",
    # Service dependencies
    "build_service_dependency_graph",
    "calculate_critical_path_contribution",
    "correlate_metrics_with_traces_via_exemplars",
    # Cross-signal correlation
    "correlate_trace_with_metrics",
    "detect_circular_dependencies",
    "find_bottleneck_services",
]
