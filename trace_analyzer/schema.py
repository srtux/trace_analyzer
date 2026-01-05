"""Pydantic schemas for Cloud Trace Analyzer structured outputs."""

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
