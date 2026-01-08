"""Tests for SRE pattern detection tools."""

from unittest.mock import patch

import pytest


def make_span(
    span_id: str,
    name: str,
    start_time: str,
    end_time: str,
    parent_span_id: str | None = None,
    labels: dict | None = None,
):
    """Helper to create a mock span."""
    return {
        "span_id": span_id,
        "name": name,
        "start_time": start_time,
        "end_time": end_time,
        "parent_span_id": parent_span_id,
        "labels": labels or {},
    }


def make_trace(trace_id: str, spans: list, duration_ms: float = 1000):
    """Helper to create a mock trace."""
    return {
        "trace_id": trace_id,
        "spans": spans,
        "duration_ms": duration_ms,
    }


class TestRetryStormDetection:
    """Tests for detect_retry_storm function."""

    @patch("trace_analyzer.tools.sre_patterns.fetch_trace_data")
    def test_detects_retry_storm_with_repeated_spans(self, mock_fetch):
        """Test detection of retry storm with many repeated spans."""
        from trace_analyzer.tools.sre_patterns import detect_retry_storm

        # Create trace with 5 sequential "db_query" spans (indicates retries)
        spans = [
            make_span("1", "db_query", "2024-01-01T10:00:00.000Z", "2024-01-01T10:00:00.050Z"),
            make_span("2", "db_query", "2024-01-01T10:00:00.060Z", "2024-01-01T10:00:00.110Z"),
            make_span("3", "db_query", "2024-01-01T10:00:00.120Z", "2024-01-01T10:00:00.170Z"),
            make_span("4", "db_query", "2024-01-01T10:00:00.180Z", "2024-01-01T10:00:00.230Z"),
            make_span("5", "db_query", "2024-01-01T10:00:00.240Z", "2024-01-01T10:00:00.290Z"),
        ]
        mock_fetch.return_value = make_trace("test-trace", spans)

        result = detect_retry_storm("test-trace")

        assert result["has_retry_storm"] is True
        assert result["patterns_found"] >= 1
        assert any(p["span_name"] == "db_query" for p in result["retry_patterns"])

    @patch("trace_analyzer.tools.sre_patterns.fetch_trace_data")
    def test_detects_explicit_retry_span_names(self, mock_fetch):
        """Test detection of spans with 'retry' in the name."""
        from trace_analyzer.tools.sre_patterns import detect_retry_storm

        spans = [
            make_span("1", "api_call_retry_1", "2024-01-01T10:00:00.000Z", "2024-01-01T10:00:00.100Z"),
            make_span("2", "api_call_retry_2", "2024-01-01T10:00:00.200Z", "2024-01-01T10:00:00.300Z"),
        ]
        mock_fetch.return_value = make_trace("test-trace", spans)

        result = detect_retry_storm("test-trace", threshold=1)

        assert result["has_retry_storm"] is True

    @patch("trace_analyzer.tools.sre_patterns.fetch_trace_data")
    def test_no_retry_storm_with_unique_spans(self, mock_fetch):
        """Test that unique spans don't trigger false positive."""
        from trace_analyzer.tools.sre_patterns import detect_retry_storm

        spans = [
            make_span("1", "user_service", "2024-01-01T10:00:00.000Z", "2024-01-01T10:00:00.100Z"),
            make_span("2", "order_service", "2024-01-01T10:00:00.100Z", "2024-01-01T10:00:00.200Z"),
            make_span("3", "payment_service", "2024-01-01T10:00:00.200Z", "2024-01-01T10:00:00.300Z"),
        ]
        mock_fetch.return_value = make_trace("test-trace", spans)

        result = detect_retry_storm("test-trace")

        assert result["has_retry_storm"] is False
        assert result["patterns_found"] == 0


class TestCascadingTimeoutDetection:
    """Tests for detect_cascading_timeout function."""

    @patch("trace_analyzer.tools.sre_patterns.fetch_trace_data")
    def test_detects_cascading_timeout_pattern(self, mock_fetch):
        """Test detection of cascading timeouts in parent-child relationship."""
        from trace_analyzer.tools.sre_patterns import detect_cascading_timeout

        # Child span times out, then parent times out
        spans = [
            make_span(
                "parent",
                "api_handler_timeout",
                "2024-01-01T10:00:00.000Z",
                "2024-01-01T10:00:05.000Z",  # 5 second duration (timeout)
            ),
            make_span(
                "child",
                "db_query_timeout",
                "2024-01-01T10:00:00.100Z",
                "2024-01-01T10:00:04.900Z",  # Almost 5 seconds
                parent_span_id="parent",
                labels={"error.type": "timeout"},
            ),
        ]
        mock_fetch.return_value = make_trace("test-trace", spans)

        result = detect_cascading_timeout("test-trace", timeout_threshold_ms=1000)

        assert result["timeout_spans_count"] >= 1

    @patch("trace_analyzer.tools.sre_patterns.fetch_trace_data")
    def test_detects_timeout_by_label(self, mock_fetch):
        """Test detection of timeout via labels."""
        from trace_analyzer.tools.sre_patterns import detect_cascading_timeout

        spans = [
            make_span(
                "1",
                "external_api_call",
                "2024-01-01T10:00:00.000Z",
                "2024-01-01T10:00:30.000Z",
                labels={"error": "deadline exceeded", "error.type": "timeout"},
            ),
        ]
        mock_fetch.return_value = make_trace("test-trace", spans)

        result = detect_cascading_timeout("test-trace", timeout_threshold_ms=1000)

        assert result["timeout_spans_count"] >= 1

    @patch("trace_analyzer.tools.sre_patterns.fetch_trace_data")
    def test_no_cascade_with_fast_spans(self, mock_fetch):
        """Test that fast spans don't trigger timeout detection."""
        from trace_analyzer.tools.sre_patterns import detect_cascading_timeout

        spans = [
            make_span("1", "fast_query", "2024-01-01T10:00:00.000Z", "2024-01-01T10:00:00.050Z"),
            make_span("2", "fast_service", "2024-01-01T10:00:00.060Z", "2024-01-01T10:00:00.100Z"),
        ]
        mock_fetch.return_value = make_trace("test-trace", spans)

        result = detect_cascading_timeout("test-trace", timeout_threshold_ms=1000)

        assert result["cascade_detected"] is False


class TestConnectionPoolIssueDetection:
    """Tests for detect_connection_pool_issues function."""

    @patch("trace_analyzer.tools.sre_patterns.fetch_trace_data")
    def test_detects_long_connection_wait(self, mock_fetch):
        """Test detection of long connection pool wait times."""
        from trace_analyzer.tools.sre_patterns import detect_connection_pool_issues

        spans = [
            make_span(
                "1",
                "connection_pool_acquire",
                "2024-01-01T10:00:00.000Z",
                "2024-01-01T10:00:00.500Z",  # 500ms wait
                labels={"pool.size": "10", "pool.active": "10"},
            ),
        ]
        mock_fetch.return_value = make_trace("test-trace", spans)

        result = detect_connection_pool_issues("test-trace", wait_threshold_ms=100)

        assert result["issues_found"] >= 1
        assert result["pool_issues"][0]["wait_duration_ms"] == 500.0

    @patch("trace_analyzer.tools.sre_patterns.fetch_trace_data")
    def test_no_issues_with_fast_connection_acquire(self, mock_fetch):
        """Test that fast connection acquisitions don't trigger issues."""
        from trace_analyzer.tools.sre_patterns import detect_connection_pool_issues

        spans = [
            make_span(
                "1",
                "connection_pool_checkout",
                "2024-01-01T10:00:00.000Z",
                "2024-01-01T10:00:00.005Z",  # 5ms - fast
            ),
        ]
        mock_fetch.return_value = make_trace("test-trace", spans)

        result = detect_connection_pool_issues("test-trace", wait_threshold_ms=100)

        assert result["issues_found"] == 0
        assert result["has_pool_exhaustion"] is False


class TestAllPatternsDetection:
    """Tests for detect_all_sre_patterns comprehensive scan."""

    @patch("trace_analyzer.tools.sre_patterns.fetch_trace_data")
    def test_comprehensive_scan_healthy_trace(self, mock_fetch):
        """Test that healthy trace returns healthy status."""
        from trace_analyzer.tools.sre_patterns import detect_all_sre_patterns

        spans = [
            make_span("1", "api_handler", "2024-01-01T10:00:00.000Z", "2024-01-01T10:00:00.100Z"),
            make_span("2", "db_query", "2024-01-01T10:00:00.010Z", "2024-01-01T10:00:00.050Z", "1"),
            make_span("3", "cache_lookup", "2024-01-01T10:00:00.060Z", "2024-01-01T10:00:00.070Z", "1"),
        ]
        mock_fetch.return_value = make_trace("test-trace", spans)

        result = detect_all_sre_patterns("test-trace")

        assert result["overall_health"] == "healthy"
        assert result["patterns_detected"] == 0

    @patch("trace_analyzer.tools.sre_patterns.fetch_trace_data")
    def test_handles_fetch_error(self, mock_fetch):
        """Test that fetch errors are handled gracefully."""
        from trace_analyzer.tools.sre_patterns import detect_all_sre_patterns

        mock_fetch.return_value = {"error": "Trace not found"}

        result = detect_all_sre_patterns("nonexistent-trace")

        assert "error" in result
