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

from .cross_signal import (
    correlate_trace_with_metrics,
    correlate_metrics_with_traces_via_exemplars,
    build_cross_signal_timeline,
    analyze_signal_correlation_strength,
)
from .critical_path import (
    analyze_critical_path,
    find_bottleneck_services,
    calculate_critical_path_contribution,
)
from .dependencies import (
    build_service_dependency_graph,
    analyze_upstream_downstream_impact,
    detect_circular_dependencies,
)

__all__ = [
    # Cross-signal correlation
    "correlate_trace_with_metrics",
    "correlate_metrics_with_traces_via_exemplars",
    "build_cross_signal_timeline",
    "analyze_signal_correlation_strength",
    # Critical path analysis
    "analyze_critical_path",
    "find_bottleneck_services",
    "calculate_critical_path_contribution",
    # Service dependencies
    "build_service_dependency_graph",
    "analyze_upstream_downstream_impact",
    "detect_circular_dependencies",
]
