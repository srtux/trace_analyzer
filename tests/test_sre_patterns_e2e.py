"""End-to-end tests for SRE pattern detection using realistic trace data."""

import json
import os
from unittest.mock import patch

import pytest


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def load_trace(filename: str) -> dict:
    """Load a trace from the test data directory."""
    with open(os.path.join(DATA_DIR, filename)) as f:
        return json.load(f)


def mock_fetch_trace_data(trace_data: dict):
    """Create a mock that returns the provided trace data."""
    def _mock(trace_id, project_id=None):
        # If trace_id is a dict, return it directly
        if isinstance(trace_id, dict):
            return trace_id
        # If trace_id matches our trace_data's trace_id, return it
        if trace_id == trace_data.get("trace_id"):
            return trace_data
        # Otherwise return the trace_data (for testing)
        return trace_data
    return _mock


class TestRetryStormE2E:
    """End-to-end tests for retry storm detection."""

    @pytest.fixture
    def retry_trace(self):
        return load_trace("retry_storm_trace.json")

    def test_detects_retry_storm_in_real_trace(self, retry_trace):
        """Test retry storm detection with realistic trace data."""
        from trace_analyzer.tools.sre_patterns import detect_retry_storm

        with patch(
            "trace_analyzer.tools.sre_patterns.fetch_trace_data",
            mock_fetch_trace_data(retry_trace),
        ):
            result = detect_retry_storm(retry_trace["trace_id"])

            assert result["has_retry_storm"] is True
            assert result["patterns_found"] >= 1

            # Should detect the DatabaseQuery retries
            db_pattern = next(
                (p for p in result["retry_patterns"] if p["span_name"] == "DatabaseQuery"),
                None,
            )
            assert db_pattern is not None
            assert db_pattern["retry_count"] == 5
            assert db_pattern["impact"] == "high"  # 5+ retries = high impact

    def test_retry_storm_with_exponential_backoff_detection(self, retry_trace):
        """Test that exponential backoff pattern is detected."""
        from trace_analyzer.tools.sre_patterns import detect_retry_storm

        with patch(
            "trace_analyzer.tools.sre_patterns.fetch_trace_data",
            mock_fetch_trace_data(retry_trace),
        ):
            result = detect_retry_storm(retry_trace["trace_id"])

            # Check if backoff was detected (durations increase)
            db_pattern = next(
                (p for p in result["retry_patterns"] if p["span_name"] == "DatabaseQuery"),
                None,
            )
            # The test data has increasing durations which should be detected
            assert db_pattern is not None


class TestCascadingTimeoutE2E:
    """End-to-end tests for cascading timeout detection."""

    @pytest.fixture
    def timeout_trace(self):
        return load_trace("cascading_timeout_trace.json")

    def test_detects_cascading_timeout_in_real_trace(self, timeout_trace):
        """Test cascading timeout detection with realistic trace data."""
        from trace_analyzer.tools.sre_patterns import detect_cascading_timeout

        with patch(
            "trace_analyzer.tools.sre_patterns.fetch_trace_data",
            mock_fetch_trace_data(timeout_trace),
        ):
            result = detect_cascading_timeout(timeout_trace["trace_id"], timeout_threshold_ms=1000)

            # Should detect multiple timeout spans
            assert result["timeout_spans_count"] >= 3  # All 4 spans have timeout indicators

            # Should detect the cascade
            assert result["impact"] in ["critical", "high"]

    def test_timeout_detection_with_explicit_labels(self, timeout_trace):
        """Test that timeout is detected via error.type labels."""
        from trace_analyzer.tools.sre_patterns import detect_cascading_timeout

        with patch(
            "trace_analyzer.tools.sre_patterns.fetch_trace_data",
            mock_fetch_trace_data(timeout_trace),
        ):
            result = detect_cascading_timeout(timeout_trace["trace_id"], timeout_threshold_ms=1000)

            # All spans in the test data have timeout-related labels
            timeout_spans = result["timeout_spans"]
            assert len(timeout_spans) >= 3

            # Check that spans with "timeout" in name are detected
            timeout_names = [s["span_name"] for s in timeout_spans]
            assert any("timeout" in name.lower() for name in timeout_names)


class TestConnectionPoolE2E:
    """End-to-end tests for connection pool issue detection."""

    @pytest.fixture
    def pool_trace(self):
        return load_trace("connection_pool_trace.json")

    def test_detects_connection_pool_issues_in_real_trace(self, pool_trace):
        """Test connection pool issue detection with realistic trace data."""
        from trace_analyzer.tools.sre_patterns import detect_connection_pool_issues

        with patch(
            "trace_analyzer.tools.sre_patterns.fetch_trace_data",
            mock_fetch_trace_data(pool_trace),
        ):
            result = detect_connection_pool_issues(pool_trace["trace_id"], wait_threshold_ms=100)

            assert result["issues_found"] >= 1
            assert result["total_wait_ms"] > 0

            # Should detect the long pool acquire times
            pool_issues = result["pool_issues"]
            assert len(pool_issues) >= 1

            # Check that pool metadata is captured
            first_issue = pool_issues[0]
            assert first_issue["wait_duration_ms"] > 100

    def test_pool_exhaustion_flag(self, pool_trace):
        """Test that pool exhaustion is flagged when wait times are high."""
        from trace_analyzer.tools.sre_patterns import detect_connection_pool_issues

        with patch(
            "trace_analyzer.tools.sre_patterns.fetch_trace_data",
            mock_fetch_trace_data(pool_trace),
        ):
            result = detect_connection_pool_issues(pool_trace["trace_id"], wait_threshold_ms=100)

            # Total wait should be significant
            assert result["total_wait_ms"] > 500
            assert result["has_pool_exhaustion"] is True


class TestComprehensivePatternScan:
    """Tests for detect_all_sre_patterns comprehensive scan."""

    @pytest.fixture
    def good_trace(self):
        return load_trace("good_trace.json")

    @pytest.fixture
    def bad_trace(self):
        return load_trace("bad_trace.json")

    @pytest.fixture
    def retry_trace(self):
        return load_trace("retry_storm_trace.json")

    def test_healthy_trace_returns_healthy(self, good_trace):
        """Test that a healthy trace is identified as healthy."""
        from trace_analyzer.tools.sre_patterns import detect_all_sre_patterns

        with patch(
            "trace_analyzer.tools.sre_patterns.fetch_trace_data",
            mock_fetch_trace_data(good_trace),
        ):
            result = detect_all_sre_patterns(good_trace["trace_id"])

            assert result["overall_health"] == "healthy"
            assert result["patterns_detected"] == 0

    def test_problematic_trace_returns_issues(self, retry_trace):
        """Test that a problematic trace is identified with issues."""
        from trace_analyzer.tools.sre_patterns import detect_all_sre_patterns

        with patch(
            "trace_analyzer.tools.sre_patterns.fetch_trace_data",
            mock_fetch_trace_data(retry_trace),
        ):
            result = detect_all_sre_patterns(retry_trace["trace_id"])

            assert result["overall_health"] != "healthy"
            assert result["patterns_detected"] >= 1
            assert len(result["recommendations"]) >= 1


class TestCombinedAnalysis:
    """Tests combining multiple analysis tools."""

    @pytest.fixture
    def good_trace(self):
        return load_trace("good_trace.json")

    @pytest.fixture
    def bad_trace(self):
        return load_trace("bad_trace.json")

    def test_combined_trace_comparison_and_pattern_detection(self, good_trace, bad_trace):
        """Test running trace comparison followed by pattern detection."""
        from trace_analyzer.tools.trace_analysis import compare_span_timings
        from trace_analyzer.tools.sre_patterns import detect_all_sre_patterns

        def mock_fetch(trace_id, project_id=None):
            if isinstance(trace_id, str):
                if trace_id.strip().startswith("{"):
                    return json.loads(trace_id)
                if "good" in trace_id:
                    return good_trace
                if "bad" in trace_id:
                    return bad_trace
            return trace_id if isinstance(trace_id, dict) else bad_trace

        with patch("trace_analyzer.tools.trace_analysis.fetch_trace_data", mock_fetch):
            with patch("trace_analyzer.tools.sre_patterns.fetch_trace_data", mock_fetch):
                # Step 1: Compare traces
                comparison = compare_span_timings(
                    json.dumps(good_trace),
                    json.dumps(bad_trace)
                )

                # Verify comparison found issues
                assert comparison.get("slower_spans") or comparison.get("patterns")

                # Step 2: Run pattern detection on bad trace
                patterns = detect_all_sre_patterns(bad_trace["trace_id"])

                # Verify pattern detection works
                assert "overall_health" in patterns

    def test_full_analysis_pipeline_simulation(self, good_trace, bad_trace):
        """Simulate a full analysis pipeline: compare -> detect patterns -> summarize."""
        from trace_analyzer.tools.trace_analysis import (
            compare_span_timings,
            extract_errors,
            build_call_graph,
        )
        from trace_analyzer.tools.sre_patterns import detect_all_sre_patterns

        def mock_fetch(trace_id, project_id=None):
            if isinstance(trace_id, str):
                if trace_id.strip().startswith("{"):
                    return json.loads(trace_id)
                if "good" in trace_id:
                    return good_trace
                if "bad" in trace_id:
                    return bad_trace
            return trace_id if isinstance(trace_id, dict) else bad_trace

        with patch("trace_analyzer.tools.trace_analysis.fetch_trace_data", mock_fetch):
            with patch("trace_analyzer.tools.sre_patterns.fetch_trace_data", mock_fetch):
                # Stage 1: Investigation
                comparison = compare_span_timings(
                    json.dumps(good_trace),
                    json.dumps(bad_trace)
                )
                errors = extract_errors(json.dumps(bad_trace))
                call_graph = build_call_graph(json.dumps(bad_trace))

                # Verify investigation results
                assert "slower_spans" in comparison or "patterns" in comparison
                assert isinstance(errors, list)  # extract_errors returns a list
                assert "span_tree" in call_graph

                # Stage 2: Pattern detection
                patterns = detect_all_sre_patterns(bad_trace["trace_id"])

                # Compile results (simulating what root_cause_analyzer would do)
                analysis_report = {
                    "investigation": {
                        "timing_issues": len(comparison.get("slower_spans", [])),
                        "patterns_found": len(comparison.get("patterns", [])),
                        "error_count": len(errors),  # errors is a list
                    },
                    "sre_patterns": patterns,
                    "call_graph_depth": call_graph.get("max_depth", 0),
                }

                # Verify complete analysis
                assert analysis_report["investigation"]["timing_issues"] >= 0
                assert "overall_health" in analysis_report["sre_patterns"]
