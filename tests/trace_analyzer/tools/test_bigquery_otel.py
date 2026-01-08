"""Tests for BigQuery OpenTelemetry analysis tools."""

import json
import pytest

from trace_analyzer.tools.bigquery_otel import (
    analyze_aggregate_metrics,
    compare_time_periods,
    correlate_logs_with_trace,
    detect_trend_changes,
    find_exemplar_traces,
)


class TestBigQueryOtelTools:
    """Tests for BigQuery OTEL tools that generate SQL queries."""

    def test_analyze_aggregate_metrics_basic(self):
        """Test basic aggregate metrics SQL generation."""
        result = analyze_aggregate_metrics(
            dataset_id="myproject.telemetry",
            time_window_hours=24
        )

        result_data = json.loads(result)

        assert "sql_query" in result_data
        assert "SELECT" in result_data["sql_query"]
        assert "myproject.telemetry.otel_traces" in result_data["sql_query"]
        assert "24 HOUR" in result_data["sql_query"]
        assert "parent_span_id IS NULL" in result_data["sql_query"]  # Root spans only

    def test_analyze_aggregate_metrics_with_service_filter(self):
        """Test aggregate metrics with service name filter."""
        result = analyze_aggregate_metrics(
            dataset_id="myproject.telemetry",
            service_name="payment-service",
            time_window_hours=12
        )

        result_data = json.loads(result)

        assert "sql_query" in result_data
        assert "service_name = 'payment-service'" in result_data["sql_query"]
        assert "12 HOUR" in result_data["sql_query"]

    def test_find_exemplar_traces_outliers(self):
        """Test finding outlier traces."""
        result = find_exemplar_traces(
            dataset_id="myproject.telemetry",
            selection_strategy="outliers",
            limit=10
        )

        result_data = json.loads(result)

        assert result_data["selection_strategy"] == "outliers"
        assert "sql_query" in result_data
        assert "p95_ms" in result_data["sql_query"]
        assert "LIMIT 10" in result_data["sql_query"]

    def test_find_exemplar_traces_errors(self):
        """Test finding error traces."""
        result = find_exemplar_traces(
            dataset_id="myproject.telemetry",
            selection_strategy="errors",
            limit=5
        )

        result_data = json.loads(result)

        assert result_data["selection_strategy"] == "errors"
        assert "status_code = 'ERROR'" in result_data["sql_query"]
        assert "LIMIT 5" in result_data["sql_query"]

    def test_find_exemplar_traces_baseline(self):
        """Test finding baseline (P50) traces."""
        result = find_exemplar_traces(
            dataset_id="myproject.telemetry",
            selection_strategy="baseline"
        )

        result_data = json.loads(result)

        assert result_data["selection_strategy"] == "baseline"
        assert "p50_ms" in result_data["sql_query"]
        assert "status_code != 'ERROR'" in result_data["sql_query"]

    def test_find_exemplar_traces_comparison(self):
        """Test finding both baseline and outlier traces."""
        result = find_exemplar_traces(
            dataset_id="myproject.telemetry",
            selection_strategy="comparison",
            limit=20
        )

        result_data = json.loads(result)

        assert result_data["selection_strategy"] == "comparison"
        assert "baseline_traces" in result_data["sql_query"]
        assert "outlier_traces" in result_data["sql_query"]
        assert "UNION ALL" in result_data["sql_query"]

    def test_find_exemplar_traces_invalid_strategy(self):
        """Test invalid selection strategy."""
        result = find_exemplar_traces(
            dataset_id="myproject.telemetry",
            selection_strategy="invalid_strategy"
        )

        result_data = json.loads(result)

        assert "error" in result_data
        assert "Unknown selection_strategy" in result_data["error"]

    def test_correlate_logs_with_trace_basic(self):
        """Test log correlation query generation."""
        result = correlate_logs_with_trace(
            dataset_id="myproject.telemetry",
            trace_id="abc123def456",
            include_nearby_logs=False
        )

        result_data = json.loads(result)

        assert result_data["trace_id"] == "abc123def456"
        assert "sql_query" in result_data
        assert "abc123def456" in result_data["sql_query"]
        assert "direct_logs" in result_data["sql_query"]

    def test_correlate_logs_with_trace_nearby(self):
        """Test log correlation with nearby logs."""
        result = correlate_logs_with_trace(
            dataset_id="myproject.telemetry",
            trace_id="abc123def456",
            include_nearby_logs=True,
            time_window_seconds=60
        )

        result_data = json.loads(result)

        assert "nearby_logs" in result_data["sql_query"]
        assert "60 SECOND" in result_data["sql_query"]
        assert "UNION ALL" in result_data["sql_query"]

    def test_compare_time_periods_basic(self):
        """Test time period comparison."""
        result = compare_time_periods(
            dataset_id="myproject.telemetry",
            baseline_hours_ago_start=48,
            baseline_hours_ago_end=24,
            anomaly_hours_ago_start=24,
            anomaly_hours_ago_end=0
        )

        result_data = json.loads(result)

        assert "sql_query" in result_data
        assert "baseline_period" in result_data["sql_query"]
        assert "anomaly_period" in result_data["sql_query"]
        assert "48 HOUR" in result_data["sql_query"]
        assert "24 HOUR" in result_data["sql_query"]

    def test_compare_time_periods_with_service(self):
        """Test time period comparison with service filter."""
        result = compare_time_periods(
            dataset_id="myproject.telemetry",
            service_name="checkout-service"
        )

        result_data = json.loads(result)

        assert "service_name = 'checkout-service'" in result_data["sql_query"]

    def test_detect_trend_changes_p95(self):
        """Test trend detection for P95 latency."""
        result = detect_trend_changes(
            dataset_id="myproject.telemetry",
            time_window_hours=72,
            bucket_hours=1,
            metric="p95"
        )

        result_data = json.loads(result)

        assert result_data["metric"] == "p95"
        assert "APPROX_QUANTILES" in result_data["sql_query"]
        assert "[OFFSET(95)]" in result_data["sql_query"]
        assert "p95_latency_ms" in result_data["sql_query"]
        assert "SIGNIFICANT_CHANGE" in result_data["sql_query"]

    def test_detect_trend_changes_error_rate(self):
        """Test trend detection for error rate."""
        result = detect_trend_changes(
            dataset_id="myproject.telemetry",
            metric="error_rate"
        )

        result_data = json.loads(result)

        assert result_data["metric"] == "error_rate"
        assert "COUNTIF(status_code = 'ERROR')" in result_data["sql_query"]
        assert "error_rate_pct" in result_data["sql_query"]

    def test_detect_trend_changes_throughput(self):
        """Test trend detection for throughput."""
        result = detect_trend_changes(
            dataset_id="myproject.telemetry",
            metric="throughput"
        )

        result_data = json.loads(result)

        assert result_data["metric"] == "throughput"
        assert "COUNT(*) as metric_value" in result_data["sql_query"]
        assert "request_count" in result_data["sql_query"]

    def test_detect_trend_changes_invalid_metric(self):
        """Test invalid metric for trend detection."""
        result = detect_trend_changes(
            dataset_id="myproject.telemetry",
            metric="invalid_metric"
        )

        result_data = json.loads(result)

        assert "error" in result_data
        assert "Unknown metric" in result_data["error"]

    def test_query_contains_proper_time_conversion(self):
        """Test that queries properly convert nanoseconds to milliseconds."""
        result = analyze_aggregate_metrics(
            dataset_id="myproject.telemetry"
        )

        result_data = json.loads(result)

        # OpenTelemetry stores duration in nanoseconds, we should convert to ms
        assert "duration / 1000000" in result_data["sql_query"]

    def test_all_queries_include_descriptions(self):
        """Test that all tool responses include descriptions and next steps."""
        tools_and_params = [
            (analyze_aggregate_metrics, {"dataset_id": "test.dataset"}),
            (find_exemplar_traces, {"dataset_id": "test.dataset"}),
            (correlate_logs_with_trace, {"dataset_id": "test.dataset", "trace_id": "abc123"}),
            (compare_time_periods, {"dataset_id": "test.dataset"}),
            (detect_trend_changes, {"dataset_id": "test.dataset"}),
        ]

        for tool_func, params in tools_and_params:
            result = tool_func(**params)
            result_data = json.loads(result)

            # Skip if error response
            if "error" in result_data:
                continue

            assert "description" in result_data, f"{tool_func.__name__} missing description"
            assert "next_steps" in result_data, f"{tool_func.__name__} missing next_steps"
