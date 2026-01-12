"""Sub-agents for the SRE Agent."""

from .change import change_detective
from .logs import log_analyst
from .metrics import metrics_analyzer
from .trace import (
    aggregate_analyzer,
    causality_analyzer,
    error_analyzer,
    latency_analyzer,
    resiliency_architect,
    service_impact_analyzer,
    statistics_analyzer,
    structure_analyzer,
)

__all__ = [
    # Trace Squad
    "aggregate_analyzer",
    "latency_analyzer",
    "error_analyzer",
    "structure_analyzer",
    "statistics_analyzer",
    "causality_analyzer",
    "service_impact_analyzer",
    "resiliency_architect",
    # Change Squad
    "change_detective",
    # Log Squad
    "log_analyst",
    # Metrics Squad
    "metrics_analyzer",
]
