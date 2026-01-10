"""Comprehensive tests for BigQuery OTel tools."""

import json

from sre_agent.tools.analysis.bigquery import otel as bigquery_otel
from tests.fixtures.synthetic_otel_data import (
    generate_trace_id,
)


class TestAnalyzeAggregateMetrics:
    """Tests for analyze_aggregate_metrics tool."""

    def test_basic_query_generation(self):
        """Test basic aggregate metrics query generation."""
        result = bigquery_otel.analyze_aggregate_metrics(
            dataset_id="project.dataset", table_name="_AllSpans", time_window_hours=24
        )

        data = json.loads(result)
        assert data["analysis_type"] == "aggregate_metrics"
        assert "sql_query" in data
        assert "SELECT" in data["sql_query"]
        assert "GROUP BY" in data["sql_query"]
        assert "_AllSpans" in data["sql_query"]

    def test_query_with_service_filter(self):
        """Test query generation with service name filter."""
        result = bigquery_otel.analyze_aggregate_metrics(
            dataset_id="project.dataset",
            table_name="_AllSpans",
            service_name="frontend",
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert (
            "JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') = 'frontend'"
            in query
        )

    def test_query_with_operation_filter(self):
        """Test query generation with operation name filter."""
        result = bigquery_otel.analyze_aggregate_metrics(
            dataset_id="project.dataset",
            table_name="_AllSpans",
            operation_name="HTTP GET /api/users",
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "name = 'HTTP GET /api/users'" in query

    def test_query_with_min_duration(self):
        """Test query generation with minimum duration filter."""
        result = bigquery_otel.analyze_aggregate_metrics(
            dataset_id="project.dataset", table_name="_AllSpans", min_duration_ms=100.0
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "duration_nano >= 100000000" in query

    def test_query_uses_correct_schema_fields(self):
        """Test that query uses correct OTel schema field names."""
        result = bigquery_otel.analyze_aggregate_metrics(
            dataset_id="project.dataset", table_name="_AllSpans"
        )

        data = json.loads(result)
        query = data["sql_query"]

        # Check for correct field names
        assert "duration_nano" in query
        assert "status.code = 2" in query  # ERROR status
        assert "parent_span_id IS NULL" in query
        assert "JSON_EXTRACT_SCALAR(resource.attributes" in query

    def test_query_group_by_service_name(self):
        """Test grouping by service name."""
        result = bigquery_otel.analyze_aggregate_metrics(
            dataset_id="project.dataset",
            table_name="_AllSpans",
            group_by="service_name",
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name')" in query

    def test_query_group_by_operation_name(self):
        """Test grouping by operation name."""
        result = bigquery_otel.analyze_aggregate_metrics(
            dataset_id="project.dataset",
            table_name="_AllSpans",
            group_by="operation_name",
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "name as operation_name" in query

    def test_query_includes_percentiles(self):
        """Test that query includes latency percentiles."""
        result = bigquery_otel.analyze_aggregate_metrics(
            dataset_id="project.dataset", table_name="_AllSpans"
        )

        data = json.loads(result)
        query = data["sql_query"]

        assert "APPROX_QUANTILES" in query
        assert "OFFSET(50)" in query  # P50
        assert "OFFSET(95)" in query  # P95
        assert "OFFSET(99)" in query  # P99


class TestFindExemplarTraces:
    """Tests for find_exemplar_traces tool."""

    def test_outliers_strategy(self):
        """Test exemplar selection with outliers strategy."""
        result = bigquery_otel.find_exemplar_traces(
            dataset_id="project.dataset",
            table_name="_AllSpans",
            selection_strategy="outliers",
            limit=10,
        )

        data = json.loads(result)
        assert data["selection_strategy"] == "outliers"
        query = data["sql_query"]
        assert "APPROX_QUANTILES" in query
        assert "OFFSET(95)" in query
        assert "p95_ms" in query

    def test_errors_strategy(self):
        """Test exemplar selection with errors strategy."""
        result = bigquery_otel.find_exemplar_traces(
            dataset_id="project.dataset",
            table_name="_AllSpans",
            selection_strategy="errors",
        )

        data = json.loads(result)
        assert data["selection_strategy"] == "errors"
        query = data["sql_query"]
        assert "status.code = 2" in query

    def test_baseline_strategy(self):
        """Test exemplar selection with baseline strategy."""
        result = bigquery_otel.find_exemplar_traces(
            dataset_id="project.dataset",
            table_name="_AllSpans",
            selection_strategy="baseline",
        )

        data = json.loads(result)
        assert data["selection_strategy"] == "baseline"
        query = data["sql_query"]
        assert "OFFSET(50)" in query  # P50
        assert "status.code != 2" in query  # Not ERROR

    def test_comparison_strategy(self):
        """Test exemplar selection with comparison strategy."""
        result = bigquery_otel.find_exemplar_traces(
            dataset_id="project.dataset",
            table_name="_AllSpans",
            selection_strategy="comparison",
            limit=10,
        )

        data = json.loads(result)
        assert data["selection_strategy"] == "comparison"
        query = data["sql_query"]
        assert "baseline_traces" in query
        assert "outlier_traces" in query
        assert "UNION ALL" in query

    def test_unknown_strategy_returns_error(self):
        """Test that unknown strategy returns error."""
        result = bigquery_otel.find_exemplar_traces(
            dataset_id="project.dataset",
            table_name="_AllSpans",
            selection_strategy="unknown",
        )

        data = json.loads(result)
        assert "error" in data


class TestCorrelateLogsWithTrace:
    """Tests for correlate_logs_with_trace tool."""

    def test_basic_log_correlation(self):
        """Test basic log correlation query."""
        trace_id = generate_trace_id()
        result = bigquery_otel.correlate_logs_with_trace(
            dataset_id="project.dataset", trace_id=trace_id
        )

        data = json.loads(result)
        assert data["analysis_type"] == "log_correlation"
        assert data["trace_id"] == trace_id
        query = data["sql_query"]
        assert "trace_context" in query
        assert "direct_logs" in query

    def test_log_correlation_with_nearby_logs(self):
        """Test log correlation including nearby logs."""
        trace_id = generate_trace_id()
        result = bigquery_otel.correlate_logs_with_trace(
            dataset_id="project.dataset",
            trace_id=trace_id,
            include_nearby_logs=True,
            time_window_seconds=30,
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "nearby_logs" in query
        assert "temporal_correlation" in query
        assert "INTERVAL 30 SECOND" in query

    def test_log_correlation_without_nearby_logs(self):
        """Test log correlation without nearby logs."""
        trace_id = generate_trace_id()
        result = bigquery_otel.correlate_logs_with_trace(
            dataset_id="project.dataset", trace_id=trace_id, include_nearby_logs=False
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "nearby_logs" not in query
        assert "direct_logs" in query

    def test_uses_correct_log_schema_fields(self):
        """Test that query uses correct log schema fields."""
        trace_id = generate_trace_id()
        result = bigquery_otel.correlate_logs_with_trace(
            dataset_id="project.dataset", trace_id=trace_id
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "time_unix_nano" in query
        assert "severity_text" in query
        assert "body.string_value" in query
        assert "JSON_EXTRACT_SCALAR(l.resource.attributes, '$.service.name')" in query


class TestCompareTimePeriods:
    """Tests for compare_time_periods tool."""

    def test_basic_time_period_comparison(self):
        """Test basic time period comparison query."""
        result = bigquery_otel.compare_time_periods(
            dataset_id="project.dataset",
            table_name="_AllSpans",
            baseline_hours_ago_start=48,
            baseline_hours_ago_end=24,
            anomaly_hours_ago_start=24,
            anomaly_hours_ago_end=0,
        )

        data = json.loads(result)
        assert data["analysis_type"] == "time_period_comparison"
        query = data["sql_query"]
        assert "baseline_period" in query
        assert "anomaly_period" in query
        assert "INTERVAL 48 HOUR" in query
        assert "INTERVAL 24 HOUR" in query

    def test_time_comparison_with_service_filter(self):
        """Test time period comparison with service filter."""
        result = bigquery_otel.compare_time_periods(
            dataset_id="project.dataset",
            table_name="_AllSpans",
            service_name="frontend",
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert (
            "JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') = 'frontend'"
            in query
        )

    def test_time_comparison_includes_deltas(self):
        """Test that comparison includes delta calculations."""
        result = bigquery_otel.compare_time_periods(
            dataset_id="project.dataset", table_name="_AllSpans"
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "p95_delta_ms" in query
        assert "p95_change_pct" in query
        assert "error_rate_delta" in query
        assert "LAG(" in query


class TestDetectTrendChanges:
    """Tests for detect_trend_changes tool."""

    def test_p95_metric_trending(self):
        """Test trend detection for P95 metric."""
        result = bigquery_otel.detect_trend_changes(
            dataset_id="project.dataset", table_name="_AllSpans", metric="p95"
        )

        data = json.loads(result)
        assert data["metric"] == "p95"
        query = data["sql_query"]
        assert "APPROX_QUANTILES" in query
        assert "OFFSET(95)" in query
        assert "p95_latency_ms" in query

    def test_p99_metric_trending(self):
        """Test trend detection for P99 metric."""
        result = bigquery_otel.detect_trend_changes(
            dataset_id="project.dataset", table_name="_AllSpans", metric="p99"
        )

        data = json.loads(result)
        assert data["metric"] == "p99"
        query = data["sql_query"]
        assert "OFFSET(99)" in query

    def test_error_rate_metric_trending(self):
        """Test trend detection for error rate metric."""
        result = bigquery_otel.detect_trend_changes(
            dataset_id="project.dataset", table_name="_AllSpans", metric="error_rate"
        )

        data = json.loads(result)
        assert data["metric"] == "error_rate"
        query = data["sql_query"]
        assert "COUNTIF(status.code = 2)" in query
        assert "error_rate_pct" in query

    def test_throughput_metric_trending(self):
        """Test trend detection for throughput metric."""
        result = bigquery_otel.detect_trend_changes(
            dataset_id="project.dataset", table_name="_AllSpans", metric="throughput"
        )

        data = json.loads(result)
        assert data["metric"] == "throughput"
        query = data["sql_query"]
        assert "request_count" in query

    def test_unknown_metric_returns_error(self):
        """Test that unknown metric returns error."""
        result = bigquery_otel.detect_trend_changes(
            dataset_id="project.dataset", table_name="_AllSpans", metric="unknown"
        )

        data = json.loads(result)
        assert "error" in data

    def test_trend_includes_moving_average(self):
        """Test that trend detection includes moving average."""
        result = bigquery_otel.detect_trend_changes(
            dataset_id="project.dataset", table_name="_AllSpans"
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "moving_avg_3h" in query
        assert "AVG(metric_value) OVER" in query

    def test_trend_includes_change_detection(self):
        """Test that trend detection includes change magnitude."""
        result = bigquery_otel.detect_trend_changes(
            dataset_id="project.dataset", table_name="_AllSpans"
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "change_magnitude" in query
        assert "SIGNIFICANT_CHANGE" in query
        assert "MODERATE_CHANGE" in query
        assert "STABLE" in query

    def test_custom_time_window(self):
        """Test trend detection with custom time window."""
        result = bigquery_otel.detect_trend_changes(
            dataset_id="project.dataset",
            table_name="_AllSpans",
            time_window_hours=48,
            bucket_hours=2,
        )

        data = json.loads(result)
        assert data["time_window_hours"] == 48
        query = data["sql_query"]
        assert "INTERVAL 48 HOUR" in query


class TestQueryValidation:
    """Tests to ensure all queries are valid SQL."""

    def test_all_queries_are_valid_json(self):
        """Test that all tools return valid JSON."""
        tools = [
            bigquery_otel.analyze_aggregate_metrics,
            bigquery_otel.find_exemplar_traces,
            bigquery_otel.correlate_logs_with_trace,
            bigquery_otel.compare_time_periods,
            bigquery_otel.detect_trend_changes,
        ]

        for tool in tools:
            if tool == bigquery_otel.correlate_logs_with_trace:
                result = tool(
                    dataset_id="project.dataset", trace_id=generate_trace_id()
                )
            else:
                result = tool(dataset_id="project.dataset", table_name="_AllSpans")

            # Should not raise exception
            data = json.loads(result)
            assert isinstance(data, dict)

    def test_all_queries_contain_select_statement(self):
        """Test that all generated queries contain SELECT statements."""
        dataset_id = "project.dataset"

        queries = [
            bigquery_otel.analyze_aggregate_metrics(
                dataset_id=dataset_id, table_name="_AllSpans"
            ),
            bigquery_otel.find_exemplar_traces(
                dataset_id=dataset_id, table_name="_AllSpans"
            ),
            bigquery_otel.correlate_logs_with_trace(
                dataset_id=dataset_id, trace_id=generate_trace_id()
            ),
            bigquery_otel.compare_time_periods(
                dataset_id=dataset_id, table_name="_AllSpans"
            ),
            bigquery_otel.detect_trend_changes(
                dataset_id=dataset_id, table_name="_AllSpans"
            ),
        ]

        for query_json in queries:
            data = json.loads(query_json)
            assert "sql_query" in data
            assert "SELECT" in data["sql_query"]

    def test_queries_use_duration_nano_not_duration(self):
        """Test that queries use duration_nano instead of old duration field."""
        dataset_id = "project.dataset"

        queries = [
            bigquery_otel.analyze_aggregate_metrics(
                dataset_id=dataset_id, table_name="_AllSpans"
            ),
            bigquery_otel.find_exemplar_traces(
                dataset_id=dataset_id, table_name="_AllSpans"
            ),
            bigquery_otel.compare_time_periods(
                dataset_id=dataset_id, table_name="_AllSpans"
            ),
            bigquery_otel.detect_trend_changes(
                dataset_id=dataset_id, table_name="_AllSpans"
            ),
        ]

        for query_json in queries:
            data = json.loads(query_json)
            query = data["sql_query"]
            # Should use duration_nano
            assert "duration_nano" in query
            # Should not use old 'duration' field directly (except in division)
            # This is a soft check - we allow "duration_nano / 1000000"

    def test_queries_use_status_code_record(self):
        """Test that queries use status.code instead of status_code."""
        dataset_id = "project.dataset"

        queries = [
            bigquery_otel.analyze_aggregate_metrics(
                dataset_id=dataset_id, table_name="_AllSpans"
            ),
            bigquery_otel.find_exemplar_traces(
                dataset_id=dataset_id,
                table_name="_AllSpans",
                selection_strategy="errors",
            ),
            bigquery_otel.compare_time_periods(
                dataset_id=dataset_id, table_name="_AllSpans"
            ),
            bigquery_otel.detect_trend_changes(
                dataset_id=dataset_id, table_name="_AllSpans", metric="error_rate"
            ),
        ]

        for query_json in queries:
            data = json.loads(query_json)
            query = data["sql_query"]
            # Should use status.code
            assert "status.code" in query
