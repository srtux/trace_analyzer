"""Pydantic schemas for SRE Agent structured outputs.

This module defines Pydantic schemas for:
- Individual findings (LatencyDiff, ErrorDiff, StructureDiff)
- Sub-agent output reports (LatencyAnalysisReport, ErrorAnalysisReport, etc.)
- Aggregate report (TraceComparisonReport)
- Statistical analysis outputs
- Observability data structures (logs, metrics, errors)
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Severity level for findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Confidence(str, Enum):
    """Confidence level for analysis conclusions."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# =============================================================================
# Trace Analysis Schemas
# =============================================================================


class SpanInfo(BaseModel):
    """Information about a single span in a trace."""

    span_id: str = Field(description="Unique identifier for the span")
    name: str = Field(description="Name/operation of the span")
    duration_ms: float | None = Field(
        default=None, description="Duration in milliseconds"
    )
    parent_span_id: str | None = Field(
        default=None, description="Parent span ID if nested"
    )
    has_error: bool = Field(default=False, description="Whether this span has errors")
    labels: dict[str, str] = Field(
        default_factory=dict, description="Span labels/attributes"
    )


class LatencyDiff(BaseModel):
    """Latency difference for a specific span type."""

    span_name: str = Field(description="Name of the span being compared")
    baseline_ms: float = Field(description="Duration in baseline trace (ms)")
    target_ms: float = Field(description="Duration in target trace (ms)")
    diff_ms: float = Field(description="Difference in milliseconds")
    diff_percent: float = Field(description="Percentage change")
    severity: Severity = Field(description="Impact severity")


class ErrorDiff(BaseModel):
    """Error difference between traces."""

    span_name: str = Field(description="Span where the error occurred")
    error_type: str = Field(description="Type or category of error")
    error_message: str | None = Field(default=None, description="Error message")
    status_code: int | str | None = Field(default=None, description="Status code")
    is_new: bool = Field(description="True if this error is new")


class StructureDiff(BaseModel):
    """Structural difference in the call graph."""

    change_type: Literal["added", "removed", "modified"] = Field(
        description="Type of structural change"
    )
    span_name: str = Field(description="Name of the affected span")
    description: str = Field(description="Description of the structural change")


class TraceSummary(BaseModel):
    """Summary information for a single trace."""

    trace_id: str = Field(description="Unique trace identifier")
    span_count: int = Field(description="Total number of spans")
    total_duration_ms: float = Field(description="Total trace duration in ms")
    error_count: int = Field(default=0, description="Number of error spans")
    max_depth: int = Field(default=0, description="Maximum call tree depth")


class TraceComparisonReport(BaseModel):
    """Complete trace comparison analysis report."""

    baseline_summary: TraceSummary = Field(description="Summary of baseline trace")
    target_summary: TraceSummary = Field(description="Summary of target trace")
    overall_assessment: Literal["healthy", "degraded", "critical"] = Field(
        description="Overall health assessment"
    )
    latency_findings: list[LatencyDiff] = Field(default_factory=list)
    error_findings: list[ErrorDiff] = Field(default_factory=list)
    structure_findings: list[StructureDiff] = Field(default_factory=list)
    root_cause_hypothesis: str = Field(description="Root cause hypothesis")
    recommendations: list[str] = Field(default_factory=list)


# =============================================================================
# Sub-Agent Output Schemas
# =============================================================================


class LatencyAnalysisReport(BaseModel):
    """Output schema for the latency_analyzer sub-agent."""

    baseline_trace_id: str
    target_trace_id: str
    overall_diff_ms: float
    top_slowdowns: list[LatencyDiff] = Field(default_factory=list)
    improvements: list[LatencyDiff] = Field(default_factory=list)
    root_cause_hypothesis: str


class ErrorInfo(BaseModel):
    """Detailed information about an error occurrence."""

    span_name: str
    error_type: str
    status_code: int | str | None = None
    error_message: str | None = None
    service_name: str | None = None


class ErrorAnalysisReport(BaseModel):
    """Output schema for the error_analyzer sub-agent."""

    baseline_error_count: int
    target_error_count: int
    net_change: int
    new_errors: list[ErrorInfo] = Field(default_factory=list)
    resolved_errors: list[ErrorInfo] = Field(default_factory=list)
    common_errors: list[ErrorInfo] = Field(default_factory=list)
    error_pattern_analysis: str
    recommendations: list[str] = Field(default_factory=list)


class StructuralChange(BaseModel):
    """A single structural change in the call graph."""

    change_type: Literal["added", "removed", "depth_change", "fanout_change"]
    span_name: str
    description: str
    possible_reason: str | None = None


class StructureAnalysisReport(BaseModel):
    """Output schema for the structure_analyzer sub-agent."""

    baseline_span_count: int
    baseline_depth: int
    target_span_count: int
    target_depth: int
    missing_operations: list[StructuralChange] = Field(default_factory=list)
    new_operations: list[StructuralChange] = Field(default_factory=list)
    call_pattern_changes: list[str] = Field(default_factory=list)
    behavioral_impact: str


class LatencyDistribution(BaseModel):
    """Statistical distribution of latency values."""

    sample_size: int
    mean_ms: float
    median_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    std_dev_ms: float
    coefficient_of_variation: float


class AnomalyFinding(BaseModel):
    """A span identified as anomalous via statistical analysis."""

    span_name: str
    observed_ms: float
    expected_ms: float
    z_score: float
    severity: Severity


class CriticalPathSegment(BaseModel):
    """A segment of the critical path through a trace."""

    span_name: str
    duration_ms: float
    percentage_of_total: float
    is_optimization_target: bool = False


class StatisticalAnalysisReport(BaseModel):
    """Output schema for the statistics_analyzer sub-agent."""

    latency_distribution: LatencyDistribution
    anomaly_threshold: float
    anomalies: list[AnomalyFinding] = Field(default_factory=list)
    critical_path: list[CriticalPathSegment] = Field(default_factory=list)
    optimization_opportunities: list[str] = Field(default_factory=list)


class RootCauseCandidate(BaseModel):
    """A candidate root cause identified by causal analysis."""

    rank: int
    span_name: str
    slowdown_ms: float
    confidence: Confidence
    reasoning: str


class CausalChainLink(BaseModel):
    """A link in the causal chain showing issue propagation."""

    span_name: str
    effect_type: Literal["root_cause", "direct_effect", "cascaded_effect"]
    latency_contribution_ms: float


class CausalAnalysisReport(BaseModel):
    """Output schema for the causality_analyzer sub-agent."""

    causal_chain: list[CausalChainLink] = Field(default_factory=list)
    root_cause_candidates: list[RootCauseCandidate] = Field(default_factory=list)
    propagation_depth: int = 0
    primary_root_cause: str
    confidence: Confidence
    conclusion: str
    recommended_actions: list[str] = Field(default_factory=list)


class ServiceImpact(BaseModel):
    """Impact assessment for a single service."""

    service_name: str
    impact_type: Literal["latency", "error_rate", "throughput", "availability"]
    severity: Severity
    baseline_value: float
    current_value: float
    change_percent: float
    affected_operations: list[str] = Field(default_factory=list)


class ServiceImpactReport(BaseModel):
    """Output schema for the service_impact sub-agent."""

    total_services_analyzed: int
    impacted_services_count: int
    service_impacts: list[ServiceImpact] = Field(default_factory=list)
    cross_service_effects: list[str] = Field(default_factory=list)
    blast_radius_assessment: str


# =============================================================================
# Observability Data Schemas
# =============================================================================


class LogEntry(BaseModel):
    """Represents a single log entry from Cloud Logging."""

    timestamp: str
    severity: str
    payload: str
    resource: dict


class TimeSeriesPoint(BaseModel):
    """Represents a single point in a time series."""

    timestamp: str
    value: float


class TimeSeries(BaseModel):
    """Represents a time series from Cloud Monitoring."""

    metric: dict
    resource: dict
    points: list[TimeSeriesPoint]


class ErrorEvent(BaseModel):
    """Represents an error event from Cloud Error Reporting."""

    event_time: str
    message: str
    service_context: dict
