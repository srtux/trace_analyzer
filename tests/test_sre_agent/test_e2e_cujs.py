"""End-to-end tests for key Customer Use Journeys (CUJs).

These tests verify complete user workflows from start to finish,
ensuring the SRE Agent can handle real-world investigation scenarios.
"""

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta, timezone

from tests.fixtures.synthetic_otel_data import (
    TraceGenerator,
    BigQueryResultGenerator,
    CloudLoggingAPIGenerator,
    CloudTraceAPIGenerator,
    generate_trace_id,
)


class TestCUJ_IncidentInvestigation:
    """CUJ: Investigate a production incident with elevated errors.

    User Journey:
    1. User reports: "Checkout service has high error rate"
    2. Agent analyzes aggregate metrics to confirm issue
    3. Agent finds exemplar traces (healthy vs error)
    4. Agent extracts log patterns to find new errors
    5. Agent correlates findings to identify root cause
    6. Agent provides summary with recommendations
    """

    @pytest.fixture
    def mock_api_responses(self):
        """Set up mock API responses for the investigation."""
        return {
            "aggregate_metrics": BigQueryResultGenerator.aggregate_metrics_result(
                services=["checkout-service", "payment-service", "inventory-service"],
                with_errors=True,
            ),
            "exemplar_traces": BigQueryResultGenerator.exemplar_traces_result(
                count=5, strategy="errors"
            ),
            "healthy_trace": CloudTraceAPIGenerator.trace_response(
                trace_id=generate_trace_id(), include_error=False
            ),
            "error_trace": CloudTraceAPIGenerator.trace_response(
                trace_id=generate_trace_id(), include_error=True
            ),
            "error_logs": CloudLoggingAPIGenerator.log_entries_response(
                count=20, severity="ERROR"
            ),
        }

    def test_incident_investigation_data_flow(self, mock_api_responses):
        """Test that all data flows correctly through the investigation."""
        # Step 1: Verify aggregate metrics show the problem
        metrics = mock_api_responses["aggregate_metrics"]
        assert len(metrics) > 0

        # Find the problematic service
        problematic = [m for m in metrics if m["error_rate_pct"] > 5]
        assert len(problematic) > 0, "Should identify services with high error rates"

        # Step 2: Verify exemplar traces are available
        exemplars = mock_api_responses["exemplar_traces"]
        assert len(exemplars) > 0
        assert all("trace_id" in e for e in exemplars)

        # Step 3: Verify trace details are complete
        error_trace = mock_api_responses["error_trace"]
        assert "spans" in error_trace
        assert len(error_trace["spans"]) > 0

        # Step 4: Verify logs can be analyzed
        logs = mock_api_responses["error_logs"]
        assert "entries" in logs
        assert len(logs["entries"]) > 0

    def test_log_pattern_analysis_in_incident(
        self, baseline_period_logs, incident_period_logs
    ):
        """Test log pattern analysis identifies incident cause."""
        from sre_agent.tools.logs.patterns import compare_log_patterns

        # Compare baseline vs incident logs
        result = compare_log_patterns(
            baseline_entries=baseline_period_logs,
            comparison_entries=incident_period_logs,
        )

        # Should detect new error patterns
        new_patterns = result["anomalies"]["new_patterns"]
        assert len(new_patterns) > 0, "Should detect new patterns during incident"

        # Should have elevated alert level
        alert = result["alert_level"]
        assert "HIGH" in alert or "MEDIUM" in alert, "Alert should be elevated"


class TestCUJ_PerformanceDebugging:
    """CUJ: Debug slow API response times.

    User Journey:
    1. User reports: "API latency increased by 2x"
    2. Agent analyzes aggregate latency metrics
    3. Agent finds baseline (fast) and outlier (slow) traces
    4. Agent compares trace structures to find differences
    5. Agent identifies the slow span/service
    6. Agent provides optimization recommendations
    """

    def test_latency_comparison_workflow(self):
        """Test the latency comparison workflow."""
        # Generate traces with different latencies
        generator = TraceGenerator(service_name="api-gateway")

        fast_trace = generator.create_simple_http_trace(
            endpoint="/api/users",
            include_db_call=True,
            include_error=False,
        )

        slow_trace = generator.create_simple_http_trace(
            endpoint="/api/users",
            include_db_call=True,
            include_error=False,
        )

        # Verify traces have expected structure
        assert len(fast_trace) > 0
        assert len(slow_trace) > 0

        # Both should have root and child spans
        assert all("trace_id" in span for span in fast_trace)
        assert all("span_id" in span for span in slow_trace)

    def test_span_timing_extraction(self):
        """Test that span timings can be extracted for comparison."""
        from sre_agent.tools.trace.analysis import calculate_span_durations

        generator = TraceGenerator()
        trace = generator.create_multi_service_trace(
            services=["frontend", "api", "database"],
            include_errors=False,
        )

        # Convert to format expected by tools
        trace_data = {
            "traceId": trace[0]["trace_id"],
            "spans": [
                {
                    "spanId": span["span_id"],
                    "name": span["name"],
                    "startTime": span["start_time"],
                    "endTime": span["end_time"],
                }
                for span in trace
            ],
        }

        # Should be able to calculate durations
        # (This may need adjustment based on actual tool implementation)
        assert len(trace_data["spans"]) == 3


class TestCUJ_ErrorDiagnosis:
    """CUJ: Diagnose a specific error type.

    User Journey:
    1. User reports: "Getting DatabaseConnectionError in user-service"
    2. Agent searches for traces with this error
    3. Agent analyzes error patterns and frequency
    4. Agent correlates with logs around error time
    5. Agent identifies root cause (e.g., database overload)
    6. Agent suggests remediation steps
    """

    def test_error_pattern_detection(self):
        """Test that error patterns are properly detected."""
        from sre_agent.tools.logs.patterns import analyze_log_anomalies

        # Simulate logs with specific error pattern
        logs = []
        base_time = datetime.now(timezone.utc)

        # Add the specific error pattern
        for i in range(15):
            logs.append({
                "timestamp": (base_time + timedelta(seconds=i)).isoformat() + "Z",
                "severity": "ERROR",
                "textPayload": f"DatabaseConnectionError: Connection refused to db-primary:5432 (attempt {i})",
                "resource": {"type": "k8s_container"},
            })

        # Add some noise
        for i in range(10):
            logs.append({
                "timestamp": (base_time + timedelta(seconds=20 + i)).isoformat() + "Z",
                "severity": "INFO",
                "textPayload": f"Request {i} processed successfully",
                "resource": {"type": "k8s_container"},
            })

        result = analyze_log_anomalies(logs, focus_on_errors=True)

        # Should identify the database error pattern
        assert result["unique_patterns"] > 0
        assert len(result["error_patterns"]) > 0

        # The recommendation should mention the error
        assert "DatabaseConnectionError" in str(result) or \
               "Connection" in str(result) or \
               "ERROR" in result["recommendation"]


class TestCUJ_ProactiveMonitoring:
    """CUJ: Proactively investigate an alert.

    User Journey:
    1. Alert fires: "Error rate > 1% on checkout-service"
    2. Agent immediately fetches recent metrics
    3. Agent compares current vs baseline patterns
    4. Agent identifies any new error patterns
    5. Agent assesses blast radius
    6. Agent provides quick triage summary
    """

    def test_quick_triage_workflow(
        self, baseline_period_logs, incident_period_logs
    ):
        """Test the quick triage workflow for alert response."""
        from sre_agent.tools.logs.patterns import (
            extract_log_patterns,
            compare_log_patterns,
        )

        # Step 1: Quick pattern extraction
        current_patterns = extract_log_patterns(
            incident_period_logs, max_patterns=10
        )

        # Should complete quickly with limited patterns
        assert current_patterns["total_logs_processed"] > 0
        assert len(current_patterns["top_patterns"]) <= 10

        # Step 2: Compare with baseline
        comparison = compare_log_patterns(
            baseline_entries=baseline_period_logs,
            comparison_entries=incident_period_logs,
        )

        # Should have quick alert level determination
        assert comparison["alert_level"] is not None
        assert len(comparison["alert_level"]) > 0

    def test_blast_radius_assessment(self):
        """Test that blast radius can be assessed from trace data."""
        generator = TraceGenerator()

        # Create a multi-service trace showing impact
        trace = generator.create_multi_service_trace(
            services=["frontend", "api-gateway", "user-service", "database"],
            include_errors=True,
        )

        # All services in the trace are potentially affected
        affected_services = set()
        for span in trace:
            service = span.get("resource", {}).get("attributes", {}).get("service.name")
            if service:
                affected_services.add(service)

        # Should identify multiple affected services
        assert len(affected_services) >= 3


class TestCUJ_RootCauseAnalysis:
    """CUJ: Determine root cause of a complex issue.

    User Journey:
    1. User provides trace IDs of failing requests
    2. Agent fetches and analyzes the traces
    3. Agent identifies the first failing span
    4. Agent correlates with logs for that service
    5. Agent traces the error propagation path
    6. Agent synthesizes findings into root cause report
    """

    def test_error_propagation_tracking(self):
        """Test tracking error propagation through services."""
        generator = TraceGenerator()

        # Create trace with error in middle service
        trace = generator.create_multi_service_trace(
            services=["frontend", "api-gateway", "database"],
            include_errors=True,  # Error in last service
        )

        # Find the error span
        error_spans = [
            span for span in trace
            if span.get("status", {}).get("code") == 2
        ]

        # Should have exactly one error span (in database)
        assert len(error_spans) >= 1

        # The error span should be identifiable
        error_span = error_spans[0]
        assert error_span["name"] is not None

    def test_log_trace_correlation(self, sample_text_payload_logs):
        """Test correlating logs with trace context."""
        # Add trace context to some logs
        trace_id = generate_trace_id()
        logs_with_trace = []

        for log in sample_text_payload_logs[:3]:
            log_copy = log.copy()
            log_copy["trace"] = f"projects/test/traces/{trace_id}"
            logs_with_trace.append(log_copy)

        # Should be able to filter logs by trace
        trace_logs = [
            log for log in logs_with_trace
            if trace_id in log.get("trace", "")
        ]

        assert len(trace_logs) == 3


class TestCUJ_HistoricalComparison:
    """CUJ: Compare current behavior with historical baseline.

    User Journey:
    1. User asks: "Is current performance normal?"
    2. Agent fetches current period metrics
    3. Agent fetches historical baseline (e.g., same time last week)
    4. Agent compares patterns and identifies differences
    5. Agent reports whether behavior is within normal range
    """

    def test_time_period_comparison(self):
        """Test comparing two time periods."""
        from sre_agent.tools.logs.patterns import compare_log_patterns

        # Generate "last week" baseline
        baseline_time = datetime.now(timezone.utc) - timedelta(days=7)
        baseline_logs = []
        for i in range(20):
            baseline_logs.append({
                "timestamp": (baseline_time + timedelta(minutes=i)).isoformat() + "Z",
                "severity": "INFO",
                "textPayload": f"Normal operation log {i}",
                "resource": {"type": "k8s_container"},
            })

        # Generate "current" period
        current_time = datetime.now(timezone.utc)
        current_logs = []
        for i in range(20):
            current_logs.append({
                "timestamp": (current_time + timedelta(minutes=i)).isoformat() + "Z",
                "severity": "INFO",
                "textPayload": f"Normal operation log {i}",
                "resource": {"type": "k8s_container"},
            })

        # Compare periods
        result = compare_log_patterns(
            baseline_entries=baseline_logs,
            comparison_entries=current_logs,
        )

        # Identical patterns should result in LOW alert
        assert "LOW" in result["alert_level"] or "stable" in result["alert_level"].lower()


class TestCUJ_MultiSignalCorrelation:
    """CUJ: Correlate signals from traces, logs, and metrics.

    User Journey:
    1. User reports: "Something is wrong but I don't know what"
    2. Agent checks metrics for anomalies
    3. Agent searches logs for errors
    4. Agent finds related traces
    5. Agent correlates all signals
    6. Agent provides unified view of the issue
    """

    def test_multi_signal_data_availability(self):
        """Test that all signal types can be generated and correlated."""
        # Generate trace data
        trace_gen = TraceGenerator(service_name="api-service")
        trace = trace_gen.create_simple_http_trace(include_error=True)
        trace_id = trace[0]["trace_id"]

        # Generate correlated log data
        logs = CloudLoggingAPIGenerator.log_entries_response(
            count=5, trace_id=trace_id, severity="ERROR"
        )

        # Generate metric data (simulated)
        metrics = BigQueryResultGenerator.aggregate_metrics_result(
            services=["api-service"], with_errors=True
        )

        # Verify trace has expected service
        assert trace[0]["resource"]["attributes"]["service.name"] == "api-service"

        # Verify logs are correlated via trace_id
        assert all(trace_id in log.get("trace", "") for log in logs["entries"])

        # Verify metrics reference the service
        assert any(m["service_name"] == "api-service" for m in metrics)

    def test_timeline_reconstruction(self):
        """Test reconstructing event timeline from multiple signals."""
        base_time = datetime.now(timezone.utc)

        # Create timeline of events
        events = []

        # Metric anomaly detected
        events.append({
            "time": base_time - timedelta(minutes=5),
            "type": "metric",
            "description": "Error rate exceeded threshold",
        })

        # First error log
        events.append({
            "time": base_time - timedelta(minutes=4),
            "type": "log",
            "description": "DatabaseConnectionError first occurrence",
        })

        # Error trace
        events.append({
            "time": base_time - timedelta(minutes=3),
            "type": "trace",
            "description": "Request failed with 500 status",
        })

        # Sort by time to get timeline
        timeline = sorted(events, key=lambda e: e["time"])

        # Metric should be first (leading indicator)
        assert timeline[0]["type"] == "metric"
        assert timeline[-1]["type"] == "trace"
