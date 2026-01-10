from sre_agent.schema import (
    CausalAnalysisReport,
    Confidence,
    ErrorAnalysisReport,
    ErrorEvent,
    LatencyAnalysisReport,
    LatencyDiff,
    LatencyDistribution,
    LogEntry,
    ServiceImpactReport,
    Severity,
    SpanInfo,
    StatisticalAnalysisReport,
    StructureAnalysisReport,
    TimeSeries,
    TimeSeriesPoint,
    TraceComparisonReport,
    TraceSummary,
)


def test_span_info():
    span = SpanInfo(span_id="1", name="test")
    assert span.span_id == "1"
    assert span.name == "test"
    assert span.labels == {}


def test_trace_comparison_report():
    report = TraceComparisonReport(
        baseline_summary=TraceSummary(
            trace_id="1", span_count=1, total_duration_ms=10.0
        ),
        target_summary=TraceSummary(trace_id="2", span_count=1, total_duration_ms=20.0),
        overall_assessment="degraded",
        root_cause_hypothesis="slow DB",
        latency_findings=[
            LatencyDiff(
                span_name="db",
                baseline_ms=5.0,
                target_ms=10.0,
                diff_ms=5.0,
                diff_percent=100.0,
                severity=Severity.HIGH,
            )
        ],
    )
    assert report.overall_assessment == "degraded"
    assert len(report.latency_findings) == 1


def test_sub_agent_reports():
    # Latency
    lat_report = LatencyAnalysisReport(
        baseline_trace_id="1",
        target_trace_id="2",
        overall_diff_ms=10.0,
        root_cause_hypothesis="none",
    )
    assert lat_report.overall_diff_ms == 10.0

    # Error
    err_report = ErrorAnalysisReport(
        baseline_error_count=0,
        target_error_count=1,
        net_change=1,
        error_pattern_analysis="new error",
    )
    assert err_report.net_change == 1

    # Structure
    struct_report = StructureAnalysisReport(
        baseline_span_count=10,
        baseline_depth=3,
        target_span_count=12,
        target_depth=4,
        behavioral_impact="minor",
    )
    assert struct_report.target_depth == 4


def test_statistical_reports():
    stats = StatisticalAnalysisReport(
        latency_distribution=LatencyDistribution(
            sample_size=100,
            mean_ms=50,
            median_ms=50,
            p90_ms=80,
            p95_ms=90,
            p99_ms=100,
            std_dev_ms=10,
            coefficient_of_variation=0.2,
        ),
        anomaly_threshold=2.0,
    )
    assert stats.anomaly_threshold == 2.0


def test_causal_report():
    causal = CausalAnalysisReport(
        primary_root_cause="db", confidence=Confidence.HIGH, conclusion="db slow"
    )
    assert causal.confidence == Confidence.HIGH


def test_service_impact_report():
    impact = ServiceImpactReport(
        total_services_analyzed=5,
        impacted_services_count=1,
        blast_radius_assessment="low",
    )
    assert impact.total_services_analyzed == 5


def test_observability_schemas():
    log = LogEntry(
        timestamp="2023-01-01T00:00:00Z", severity="INFO", payload="test", resource={}
    )
    assert log.payload == "test"

    ts = TimeSeries(
        metric={}, resource={}, points=[TimeSeriesPoint(timestamp="now", value=1.0)]
    )
    assert ts.points[0].value == 1.0

    err = ErrorEvent(event_time="now", message="fail", service_context={})
    assert err.message == "fail"


def test_immutability():
    """Verify that models are immutable (frozen)."""
    import pytest
    from pydantic import ValidationError

    span = SpanInfo(span_id="1", name="test")
    with pytest.raises(ValidationError):
        span.name = "changed"

    report = TraceComparisonReport(
        baseline_summary=TraceSummary(
            trace_id="1", span_count=1, total_duration_ms=10.0
        ),
        target_summary=TraceSummary(trace_id="2", span_count=1, total_duration_ms=20.0),
        overall_assessment="degraded",
        root_cause_hypothesis="slow DB",
    )
    with pytest.raises(ValidationError):
        report.overall_assessment = "healthy"
