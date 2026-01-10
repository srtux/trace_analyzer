"""Sub-agents for specialized SRE analysis tasks.

This module provides specialized sub-agents for observability analysis:

Trace Analysis Sub-agents:
    - aggregate_analyzer: BigQuery-powered aggregate analysis
    - latency_analyzer: Span timing comparison
    - error_analyzer: Error detection and comparison
    - structure_analyzer: Call graph topology analysis
    - statistics_analyzer: Statistical outlier detection
    - causality_analyzer: Root cause determination
    - service_impact_analyzer: Blast radius assessment

Log Analysis Sub-agents:
    - log_pattern_extractor: Drain3-powered log pattern extraction
"""

from .trace import (
    aggregate_analyzer,
    latency_analyzer,
    error_analyzer,
    structure_analyzer,
    statistics_analyzer,
    causality_analyzer,
    service_impact_analyzer,
)

from .logs import log_pattern_extractor
from .metrics import metrics_analyzer

__all__ = [
    # Trace analysis
    "aggregate_analyzer",
    "latency_analyzer",
    "error_analyzer",
    "structure_analyzer",
    "statistics_analyzer",
    "causality_analyzer",
    "service_impact_analyzer",
    # Log analysis
    "log_pattern_extractor",
    # Metrics analysis
    "metrics_analyzer",
]
