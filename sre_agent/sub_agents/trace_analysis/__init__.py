"""Trace analysis sub-agents for distributed trace investigation.

This module provides 7 specialized sub-agents organized in 3 stages:

Stage 0 - Aggregate Analysis:
    - aggregate_analyzer: BigQuery-powered analysis of thousands of traces

Stage 1 - Triage (parallel):
    - latency_analyzer: Span timing comparison
    - error_analyzer: Error detection and comparison
    - structure_analyzer: Call graph topology analysis
    - statistics_analyzer: Statistical outlier detection

Stage 2 - Deep Dive (parallel):
    - causality_analyzer: Root cause determination
    - service_impact_analyzer: Blast radius assessment
"""

from .agents import (
    aggregate_analyzer,
    latency_analyzer,
    error_analyzer,
    structure_analyzer,
    statistics_analyzer,
    causality_analyzer,
    service_impact_analyzer,
)

__all__ = [
    "aggregate_analyzer",
    "latency_analyzer",
    "error_analyzer",
    "structure_analyzer",
    "statistics_analyzer",
    "causality_analyzer",
    "service_impact_analyzer",
]
