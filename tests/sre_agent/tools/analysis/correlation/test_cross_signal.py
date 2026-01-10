"""Tests for cross-signal correlation tools.

These tests verify the functionality of tools that correlate traces, logs, and metrics
using exemplars and trace context.
"""

import json
import pytest

from sre_agent.tools.analysis.correlation.cross_signal import (
    correlate_trace_with_metrics,
    correlate_metrics_with_traces_via_exemplars,
    build_cross_signal_timeline,
    analyze_signal_correlation_strength,
)


class TestCorrelateTraceWithMetrics:
    """Tests for correlate_trace_with_metrics tool."""

    def test_basic_correlation_returns_valid_json(self):
        """Test that correlate_trace_with_metrics returns valid JSON."""
        result = correlate_trace_with_metrics(
            trace_id="abc123def456",
            dataset_id="my_project.telemetry",
        )

        parsed = json.loads(result)
        assert parsed["analysis_type"] == "trace_metrics_correlation"
        assert parsed["trace_id"] == "abc123def456"
        assert "trace_context_sql" in parsed
        assert "recommended_promql_queries" in parsed

    def test_includes_trace_context_sql(self):
        """Test that SQL query for trace context is generated."""
        result = correlate_trace_with_metrics(
            trace_id="test-trace-123",
            dataset_id="project.dataset",
            trace_table_name="_AllSpans",
        )

        parsed = json.loads(result)
        sql = parsed["trace_context_sql"]

        # Verify SQL contains key elements
        assert "test-trace-123" in sql
        assert "project.dataset._AllSpans" in sql
        assert "trace_id" in sql
        assert "service_name" in sql

    def test_includes_promql_queries(self):
        """Test that recommended PromQL queries are generated."""
        result = correlate_trace_with_metrics(
            trace_id="trace-456",
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        queries = parsed["recommended_promql_queries"]

        assert len(queries) > 0
        # Each query should have metric, query, and purpose
        for q in queries:
            assert "metric" in q
            assert "query" in q
            assert "purpose" in q

    def test_service_filter_in_promql(self):
        """Test that service filter is included in PromQL when provided."""
        result = correlate_trace_with_metrics(
            trace_id="trace-789",
            dataset_id="proj.ds",
            service_name="my-service",
        )

        parsed = json.loads(result)
        queries = parsed["recommended_promql_queries"]

        # At least one query should contain the service filter
        has_service_filter = any(
            'service="my-service"' in q["query"]
            for q in queries
        )
        assert has_service_filter

    def test_custom_metrics_to_check(self):
        """Test that custom metrics list is used."""
        custom_metrics = ["custom_latency_ms", "custom_errors_total"]
        result = correlate_trace_with_metrics(
            trace_id="trace-custom",
            dataset_id="proj.ds",
            metrics_to_check=custom_metrics,
        )

        parsed = json.loads(result)
        queries = parsed["recommended_promql_queries"]

        # Should have queries for our custom metrics
        metric_names = [q["metric"] for q in queries]
        assert "custom_latency_ms" in metric_names
        assert "custom_errors_total" in metric_names

    def test_includes_correlation_strategy(self):
        """Test that correlation strategy guide is included."""
        result = correlate_trace_with_metrics(
            trace_id="trace-strat",
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "correlation_strategy" in parsed
        strategy = parsed["correlation_strategy"]

        # Should have step-by-step guidance
        assert "step_1" in strategy
        assert "step_2" in strategy

    def test_includes_exemplar_usage_guide(self):
        """Test that exemplar usage documentation is included."""
        result = correlate_trace_with_metrics(
            trace_id="trace-ex",
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "exemplar_usage" in parsed
        exemplar_guide = parsed["exemplar_usage"]

        assert "description" in exemplar_guide
        assert "how_to_use" in exemplar_guide


class TestCorrelateMetricsWithTracesViaExemplars:
    """Tests for correlate_metrics_with_traces_via_exemplars tool."""

    def test_basic_exemplar_correlation(self):
        """Test basic exemplar-based correlation."""
        result = correlate_metrics_with_traces_via_exemplars(
            dataset_id="project.telemetry",
            metric_name="http_request_duration_seconds",
            service_name="api-service",
        )

        parsed = json.loads(result)
        assert parsed["analysis_type"] == "exemplar_correlation"
        assert parsed["metric_name"] == "http_request_duration_seconds"
        assert parsed["service_name"] == "api-service"

    def test_includes_exemplar_sql(self):
        """Test that exemplar SQL query is generated."""
        result = correlate_metrics_with_traces_via_exemplars(
            dataset_id="proj.ds",
            metric_name="latency",
            service_name="svc",
            percentile_threshold=95.0,
        )

        parsed = json.loads(result)
        sql = parsed["exemplar_sql"]

        # Verify SQL contains key elements
        assert "svc" in sql
        assert "percentile_rank" in sql.lower() or "percent_rank" in sql.lower()
        assert "95" in sql  # percentile threshold

    def test_includes_histogram_bucket_analysis(self):
        """Test that SQL includes histogram bucket analysis."""
        result = correlate_metrics_with_traces_via_exemplars(
            dataset_id="proj.ds",
            metric_name="request_duration",
            service_name="frontend",
        )

        parsed = json.loads(result)
        sql = parsed["exemplar_sql"]

        # Should include bucket boundary analysis
        assert "bucket" in sql.lower() or "duration_ms" in sql.lower()

    def test_includes_promql_queries(self):
        """Test that PromQL queries for histogram analysis are included."""
        result = correlate_metrics_with_traces_via_exemplars(
            dataset_id="proj.ds",
            metric_name="http_duration",
            service_name="backend",
        )

        parsed = json.loads(result)
        assert "promql_queries" in parsed
        queries = parsed["promql_queries"]

        # Should have histogram quantile queries
        assert "histogram_quantile_p95" in queries or len(queries) > 0

    def test_different_percentile_thresholds(self):
        """Test that different percentile thresholds work."""
        for threshold in [90.0, 95.0, 99.0]:
            result = correlate_metrics_with_traces_via_exemplars(
                dataset_id="proj.ds",
                metric_name="latency",
                service_name="svc",
                percentile_threshold=threshold,
            )

            parsed = json.loads(result)
            assert parsed["percentile_threshold"] == threshold

    def test_includes_explanation(self):
        """Test that explanation of exemplars is included."""
        result = correlate_metrics_with_traces_via_exemplars(
            dataset_id="proj.ds",
            metric_name="latency",
            service_name="svc",
        )

        parsed = json.loads(result)
        assert "explanation" in parsed
        explanation = parsed["explanation"]

        assert "what_are_exemplars" in explanation
        assert "how_this_helps" in explanation


class TestBuildCrossSignalTimeline:
    """Tests for build_cross_signal_timeline tool."""

    def test_basic_timeline_generation(self):
        """Test basic timeline SQL generation."""
        result = build_cross_signal_timeline(
            trace_id="timeline-trace-123",
            dataset_id="project.telemetry",
        )

        parsed = json.loads(result)
        assert parsed["analysis_type"] == "cross_signal_timeline"
        assert parsed["trace_id"] == "timeline-trace-123"
        assert "timeline_sql" in parsed

    def test_timeline_sql_includes_spans(self):
        """Test that timeline SQL includes span events."""
        result = build_cross_signal_timeline(
            trace_id="trace-spans",
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        sql = parsed["timeline_sql"]

        assert "SPAN" in sql
        assert "trace_id" in sql.lower()

    def test_timeline_sql_includes_logs(self):
        """Test that timeline SQL includes log events."""
        result = build_cross_signal_timeline(
            trace_id="trace-logs",
            dataset_id="proj.ds",
            log_table_name="_AllLogs",
        )

        parsed = json.loads(result)
        sql = parsed["timeline_sql"]

        # Should include both direct and temporal log correlation
        assert "LOG_DIRECT" in sql or "direct_logs" in sql.lower()
        assert "LOG_TEMPORAL" in sql or "temporal_logs" in sql.lower()

    def test_custom_time_buffer(self):
        """Test that custom time buffer is used."""
        result = build_cross_signal_timeline(
            trace_id="trace-buffer",
            dataset_id="proj.ds",
            time_buffer_seconds=120,
        )

        parsed = json.loads(result)
        sql = parsed["timeline_sql"]

        # Should contain the buffer value
        assert "120" in sql

    def test_includes_event_types_documentation(self):
        """Test that event types are documented."""
        result = build_cross_signal_timeline(
            trace_id="trace-doc",
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "event_types" in parsed
        event_types = parsed["event_types"]

        assert "SPAN" in event_types
        assert "LOG_DIRECT" in event_types
        assert "LOG_TEMPORAL" in event_types

    def test_includes_reading_guide(self):
        """Test that guide for reading timeline is included."""
        result = build_cross_signal_timeline(
            trace_id="trace-guide",
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "how_to_read" in parsed


class TestAnalyzeSignalCorrelationStrength:
    """Tests for analyze_signal_correlation_strength tool."""

    def test_basic_correlation_strength_analysis(self):
        """Test basic correlation strength analysis."""
        result = analyze_signal_correlation_strength(
            dataset_id="project.telemetry",
        )

        parsed = json.loads(result)
        assert parsed["analysis_type"] == "correlation_strength"
        assert "correlation_sql" in parsed

    def test_includes_correlation_metrics(self):
        """Test that SQL calculates correlation metrics."""
        result = analyze_signal_correlation_strength(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        sql = parsed["correlation_sql"]

        # Should calculate various correlation percentages
        assert "correlation" in sql.lower() or "pct" in sql.lower()

    def test_service_filter(self):
        """Test that service filter works."""
        result = analyze_signal_correlation_strength(
            dataset_id="proj.ds",
            service_name="specific-service",
        )

        parsed = json.loads(result)
        sql = parsed["correlation_sql"]

        assert "specific-service" in sql

    def test_includes_metrics_explanation(self):
        """Test that metrics are explained."""
        result = analyze_signal_correlation_strength(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "metrics_explained" in parsed

        metrics = parsed["metrics_explained"]
        assert "log_trace_correlation_pct" in metrics

    def test_includes_score_interpretation(self):
        """Test that score interpretation guide is included."""
        result = analyze_signal_correlation_strength(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "score_interpretation" in parsed

    def test_includes_improvement_recommendations(self):
        """Test that improvement recommendations are included."""
        result = analyze_signal_correlation_strength(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "improvement_recommendations" in parsed

        recs = parsed["improvement_recommendations"]
        # Should have recommendations for different scenarios
        assert len(recs) > 0


class TestCrossSignalToolsIntegration:
    """Integration tests for cross-signal correlation tools."""

    def test_all_tools_return_valid_json(self):
        """Test that all tools return valid JSON."""
        tools_and_args = [
            (correlate_trace_with_metrics, {
                "trace_id": "test",
                "dataset_id": "proj.ds",
            }),
            (correlate_metrics_with_traces_via_exemplars, {
                "dataset_id": "proj.ds",
                "metric_name": "latency",
                "service_name": "svc",
            }),
            (build_cross_signal_timeline, {
                "trace_id": "test",
                "dataset_id": "proj.ds",
            }),
            (analyze_signal_correlation_strength, {
                "dataset_id": "proj.ds",
            }),
        ]

        for tool, args in tools_and_args:
            result = tool(**args)
            parsed = json.loads(result)
            assert isinstance(parsed, dict)
            assert "analysis_type" in parsed or "sql_query" in parsed or "correlation_sql" in parsed

    def test_all_tools_include_next_steps(self):
        """Test that all tools include next steps guidance."""
        tools_and_args = [
            (correlate_trace_with_metrics, {
                "trace_id": "test",
                "dataset_id": "proj.ds",
            }),
            (correlate_metrics_with_traces_via_exemplars, {
                "dataset_id": "proj.ds",
                "metric_name": "latency",
                "service_name": "svc",
            }),
            (build_cross_signal_timeline, {
                "trace_id": "test",
                "dataset_id": "proj.ds",
            }),
            (analyze_signal_correlation_strength, {
                "dataset_id": "proj.ds",
            }),
        ]

        for tool, args in tools_and_args:
            result = tool(**args)
            parsed = json.loads(result)
            assert "next_steps" in parsed, f"{tool.__name__} missing next_steps"

    def test_sql_queries_are_syntactically_reasonable(self):
        """Test that generated SQL queries look syntactically reasonable."""
        result = correlate_trace_with_metrics(
            trace_id="sql-test",
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        sql = parsed["trace_context_sql"]

        # Basic SQL structure checks
        assert "SELECT" in sql
        assert "FROM" in sql
        assert "WHERE" in sql
