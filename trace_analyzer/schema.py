"""Pydantic schemas for Cloud Trace Analyzer structured outputs.

This module defines Pydantic schemas for:
- Individual findings (LatencyDiff, ErrorDiff, StructureDiff)
- Sub-agent output reports (LatencyAnalysisReport, ErrorAnalysisReport, etc.)
- Aggregate report (TraceComparisonReport)
- Statistical analysis outputs

These schemas enable structured outputs from the LLM agents, ensuring
consistent data formats for downstream processing and UI rendering.
"""

from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum


class Severity(str, Enum):
    """Severity level for trace comparison findings."""
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


class SpanInfo(BaseModel):
    """Information about a single span in a trace."""
    span_id: str = Field(description="Unique identifier for the span")
    name: str = Field(description="Name/operation of the span")
    duration_ms: float | None = Field(default=None, description="Duration in milliseconds")
    parent_span_id: str | None = Field(default=None, description="Parent span ID if nested")
    has_error: bool = Field(default=False, description="Whether this span has errors")
    labels: dict[str, str] = Field(default_factory=dict, description="Span labels/attributes")


class LatencyDiff(BaseModel):
    """Latency difference for a specific span type."""
    span_name: str = Field(description="Name of the span being compared")
    baseline_ms: float = Field(description="Duration in baseline trace (ms)")
    target_ms: float = Field(description="Duration in target trace (ms)")
    diff_ms: float = Field(description="Difference in milliseconds (positive = slower)")
    diff_percent: float = Field(description="Percentage change")
    severity: Severity = Field(description="Impact severity of this latency change")


class ErrorDiff(BaseModel):
    """Error difference between traces."""
    span_name: str = Field(description="Span where the error occurred")
    error_type: str = Field(description="Type or category of error")
    error_message: str | None = Field(default=None, description="Error message if available")
    status_code: int | str | None = Field(default=None, description="HTTP/gRPC status code")
    is_new: bool = Field(description="True if this error is new in target trace")


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
    
    baseline_summary: TraceSummary = Field(description="Summary of the baseline trace")
    target_summary: TraceSummary = Field(description="Summary of the target trace")
    
    overall_assessment: Literal["healthy", "degraded", "critical"] = Field(
        description="Overall health assessment based on comparison"
    )
    
    latency_findings: list[LatencyDiff] = Field(
        default_factory=list,
        description="List of significant latency differences"
    )
    
    error_findings: list[ErrorDiff] = Field(
        default_factory=list,
        description="List of error differences"
    )
    
    structure_findings: list[StructureDiff] = Field(
        default_factory=list,
        description="List of structural/behavioral changes"
    )
    
    root_cause_hypothesis: str = Field(
        description="Hypothesis about the root cause of the differences"
    )
    
    recommendations: list[str] = Field(
        default_factory=list,
        description="Actionable recommendations based on findings"
    )


# =============================================================================
# Sub-Agent Output Schemas
# =============================================================================

class LatencyAnalysisReport(BaseModel):
    """Output schema for the latency_analyzer sub-agent."""

    baseline_trace_id: str = Field(description="Trace ID of the baseline trace")
    target_trace_id: str = Field(description="Trace ID of the target trace")
    overall_diff_ms: float = Field(
        description="Overall latency difference (positive = target is slower)"
    )
    top_slowdowns: list[LatencyDiff] = Field(
        default_factory=list,
        description="Spans with the most significant latency increases"
    )
    improvements: list[LatencyDiff] = Field(
        default_factory=list,
        description="Spans that improved (got faster) in the target"
    )
    root_cause_hypothesis: str = Field(
        description="Hypothesis about the cause of latency differences"
    )


class ErrorInfo(BaseModel):
    """Detailed information about an error occurrence."""

    span_name: str = Field(description="Name of the span where error occurred")
    error_type: str = Field(description="Type/category of the error")
    status_code: int | str | None = Field(
        default=None, description="HTTP/gRPC status code if applicable"
    )
    error_message: str | None = Field(
        default=None, description="Error message if available"
    )
    service_name: str | None = Field(
        default=None, description="Service where the error originated"
    )


class ErrorAnalysisReport(BaseModel):
    """Output schema for the error_analyzer sub-agent."""

    baseline_error_count: int = Field(description="Number of errors in baseline trace")
    target_error_count: int = Field(description="Number of errors in target trace")
    net_change: int = Field(description="Change in error count (positive = more errors)")

    new_errors: list[ErrorInfo] = Field(
        default_factory=list,
        description="Errors that appeared in target but not in baseline"
    )
    resolved_errors: list[ErrorInfo] = Field(
        default_factory=list,
        description="Errors in baseline that are absent in target"
    )
    common_errors: list[ErrorInfo] = Field(
        default_factory=list,
        description="Errors present in both traces"
    )

    error_pattern_analysis: str = Field(
        description="Analysis of error patterns (clustering, cascading, etc.)"
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Actions to address the errors"
    )


class StructuralChange(BaseModel):
    """A single structural change in the call graph."""

    change_type: Literal["added", "removed", "depth_change", "fanout_change"] = Field(
        description="Type of structural change"
    )
    span_name: str = Field(description="Name of the affected span")
    description: str = Field(description="Description of the change")
    possible_reason: str | None = Field(
        default=None, description="Hypothesis about why this change occurred"
    )


class StructureAnalysisReport(BaseModel):
    """Output schema for the structure_analyzer sub-agent."""

    baseline_span_count: int = Field(description="Number of spans in baseline")
    baseline_depth: int = Field(description="Maximum call depth in baseline")
    target_span_count: int = Field(description="Number of spans in target")
    target_depth: int = Field(description="Maximum call depth in target")

    missing_operations: list[StructuralChange] = Field(
        default_factory=list,
        description="Operations in baseline but not in target"
    )
    new_operations: list[StructuralChange] = Field(
        default_factory=list,
        description="Operations in target but not in baseline"
    )
    call_pattern_changes: list[str] = Field(
        default_factory=list,
        description="Descriptions of call pattern changes"
    )

    behavioral_impact: str = Field(
        description="Assessment of how structural changes affect system behavior"
    )


class LatencyDistribution(BaseModel):
    """Statistical distribution of latency values."""

    sample_size: int = Field(description="Number of traces/spans in the sample")
    mean_ms: float = Field(description="Mean latency in milliseconds")
    median_ms: float = Field(description="Median (P50) latency in milliseconds")
    p90_ms: float = Field(description="90th percentile latency")
    p95_ms: float = Field(description="95th percentile latency")
    p99_ms: float = Field(description="99th percentile latency")
    std_dev_ms: float = Field(description="Standard deviation")
    coefficient_of_variation: float = Field(
        description="Coefficient of variation (std_dev / mean)"
    )


class AnomalyFinding(BaseModel):
    """A span identified as anomalous via statistical analysis."""

    span_name: str = Field(description="Name of the anomalous span")
    observed_ms: float = Field(description="Observed duration")
    expected_ms: float = Field(description="Expected duration based on baseline")
    z_score: float = Field(description="Z-score indicating deviation severity")
    severity: Severity = Field(description="Severity classification")


class CriticalPathSegment(BaseModel):
    """A segment of the critical path through a trace."""

    span_name: str = Field(description="Span name")
    duration_ms: float = Field(description="Duration of this segment")
    percentage_of_total: float = Field(
        description="Percentage contribution to total trace duration"
    )
    is_optimization_target: bool = Field(
        default=False,
        description="Whether optimizing this span would reduce overall latency"
    )


class StatisticalAnalysisReport(BaseModel):
    """Output schema for the statistics_analyzer sub-agent."""

    latency_distribution: LatencyDistribution = Field(
        description="Statistical distribution of latencies"
    )

    anomaly_threshold: float = Field(
        description="Z-score threshold used for anomaly detection"
    )
    anomalies: list[AnomalyFinding] = Field(
        default_factory=list,
        description="Spans identified as statistical anomalies"
    )

    critical_path: list[CriticalPathSegment] = Field(
        default_factory=list,
        description="The critical path determining minimum latency"
    )

    optimization_opportunities: list[str] = Field(
        default_factory=list,
        description="Suggestions for latency optimization"
    )


class RootCauseCandidate(BaseModel):
    """A candidate root cause identified by causal analysis."""

    rank: int = Field(description="Ranking (1 = most likely)")
    span_name: str = Field(description="Name of the suspected root cause span")
    slowdown_ms: float = Field(description="Amount of slowdown attributed")
    confidence: Confidence = Field(description="Confidence in this being the root cause")
    reasoning: str = Field(description="Explanation of why this is a candidate")


class CausalChainLink(BaseModel):
    """A link in the causal chain showing issue propagation."""

    span_name: str = Field(description="Span in the causal chain")
    effect_type: Literal["root_cause", "direct_effect", "cascaded_effect"] = Field(
        description="Role in the causal chain"
    )
    latency_contribution_ms: float = Field(
        description="Latency contributed by this link"
    )


class CausalAnalysisReport(BaseModel):
    """Output schema for the causality_analyzer sub-agent."""

    causal_chain: list[CausalChainLink] = Field(
        default_factory=list,
        description="The identified causal chain from root to effects"
    )

    root_cause_candidates: list[RootCauseCandidate] = Field(
        default_factory=list,
        description="Ranked list of potential root causes"
    )

    propagation_depth: int = Field(
        default=0,
        description="Number of levels the issue cascaded through"
    )

    primary_root_cause: str = Field(
        description="The most likely root cause span"
    )
    confidence: Confidence = Field(
        description="Overall confidence in the analysis"
    )
    conclusion: str = Field(
        description="Summary explanation of the root cause determination"
    )

    recommended_actions: list[str] = Field(
        default_factory=list,
        description="Specific actions to address the root cause"
    )


# =============================================================================
# Service Impact Schema (for Phase 2 service_impact sub-agent)
# =============================================================================

class ServiceImpact(BaseModel):
    """Impact assessment for a single service."""

    service_name: str = Field(description="Name of the impacted service")
    impact_type: Literal["latency", "error_rate", "throughput", "availability"] = Field(
        description="Type of impact observed"
    )
    severity: Severity = Field(description="Severity of the impact")
    baseline_value: float = Field(description="Baseline metric value")
    current_value: float = Field(description="Current/target metric value")
    change_percent: float = Field(description="Percentage change from baseline")
    affected_operations: list[str] = Field(
        default_factory=list,
        description="List of operations affected in this service"
    )


class ServiceImpactReport(BaseModel):
    """Output schema for the service_impact sub-agent (Phase 2)."""

    total_services_analyzed: int = Field(
        description="Number of services analyzed"
    )
    impacted_services_count: int = Field(
        description="Number of services with notable impact"
    )

    service_impacts: list[ServiceImpact] = Field(
        default_factory=list,
        description="Impact details for each affected service"
    )

    cross_service_effects: list[str] = Field(
        default_factory=list,
        description="Effects that span multiple services"
    )

    blast_radius_assessment: str = Field(
        description="Assessment of how widely the issue affects the system"
    )


# =============================================================================
# Data Source Schemas (Logging, Monitoring, Error Reporting)
# =============================================================================

class LogEntry(BaseModel):
    """Represents a single log entry from Cloud Logging."""
    timestamp: str = Field(description="The timestamp of the log entry.")
    severity: str = Field(description="The severity of the log entry.")
    payload: str = Field(description="The payload of the log entry.")
    resource: dict = Field(description="The resource associated with the log entry.")

class TimeSeriesPoint(BaseModel):
    """Represents a single point in a time series."""
    timestamp: str = Field(description="The timestamp of the data point.")
    value: float = Field(description="The value of the data point.")

class TimeSeries(BaseModel):
    """Represents a time series from Cloud Monitoring."""
    metric: dict = Field(description="The metric descriptor.")
    resource: dict = Field(description="The resource descriptor.")
    points: list[TimeSeriesPoint] = Field(description="The data points in the time series.")

class ErrorEvent(BaseModel):
    """Represents an error event from Cloud Error Reporting."""
    event_time: str = Field(description="The timestamp of the error event.")
    message: str = Field(description="The error message.")
    service_context: dict = Field(description="The service context of the error.")
