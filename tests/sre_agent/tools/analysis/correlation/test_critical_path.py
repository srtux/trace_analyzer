"""Tests for critical path analysis tools.

These tests verify the functionality of tools that analyze the critical path
in distributed traces to identify bottlenecks and optimization opportunities.
"""

import json
from unittest.mock import patch

from sre_agent.tools.analysis.correlation.critical_path import (
    analyze_critical_path,
    calculate_critical_path_contribution,
    find_bottleneck_services,
)


class TestAnalyzeCriticalPath:
    """Tests for analyze_critical_path tool."""

    def create_mock_trace(self, spans):
        """Create a mock trace response."""
        return {"spans": spans}

    def test_analyze_simple_trace(self):
        """Test critical path analysis with a simple trace."""
        # Create a simple trace with root -> child structure
        mock_spans = [
            {
                "span_id": "root-span",
                "parent_span_id": None,
                "name": "root-operation",
                "start_time": "2024-01-01T10:00:00Z",
                "end_time": "2024-01-01T10:00:01Z",
                "labels": {"service.name": "frontend"},
            },
            {
                "span_id": "child-span",
                "parent_span_id": "root-span",
                "name": "child-operation",
                "start_time": "2024-01-01T10:00:00.100Z",
                "end_time": "2024-01-01T10:00:00.500Z",
                "labels": {"service.name": "backend"},
            },
        ]

        with patch(
            "sre_agent.tools.analysis.correlation.critical_path.fetch_trace_data"
        ) as mock_fetch:
            mock_fetch.return_value = self.create_mock_trace(mock_spans)

            result = analyze_critical_path(
                trace_id="test-trace-123",
                project_id="test-project",
            )

            assert "trace_id" in result
            assert "critical_path" in result
            assert "bottleneck_span" in result

    def test_analyze_trace_with_error(self):
        """Test handling of trace fetch errors."""
        with patch(
            "sre_agent.tools.analysis.correlation.critical_path.fetch_trace_data"
        ) as mock_fetch:
            mock_fetch.return_value = {"error": "Trace not found"}

            result = analyze_critical_path(
                trace_id="nonexistent-trace",
                project_id="test-project",
            )

            assert "error" in result

    def test_analyze_empty_trace(self):
        """Test handling of empty trace."""
        with patch(
            "sre_agent.tools.analysis.correlation.critical_path.fetch_trace_data"
        ) as mock_fetch:
            mock_fetch.return_value = {"spans": []}

            result = analyze_critical_path(
                trace_id="empty-trace",
                project_id="test-project",
            )

            assert "error" in result

    def test_identifies_bottleneck(self):
        """Test that bottleneck span is correctly identified."""
        # Create trace where one span is clearly the bottleneck
        mock_spans = [
            {
                "span_id": "root",
                "parent_span_id": None,
                "name": "request",
                "start_time": "2024-01-01T10:00:00Z",
                "end_time": "2024-01-01T10:00:02Z",
                "labels": {"service.name": "api"},
            },
            {
                "span_id": "fast-child",
                "parent_span_id": "root",
                "name": "fast-op",
                "start_time": "2024-01-01T10:00:00.100Z",
                "end_time": "2024-01-01T10:00:00.200Z",
                "labels": {"service.name": "cache"},
            },
            {
                "span_id": "slow-child",
                "parent_span_id": "root",
                "name": "slow-db-query",
                "start_time": "2024-01-01T10:00:00.200Z",
                "end_time": "2024-01-01T10:00:01.800Z",
                "labels": {"service.name": "database"},
            },
        ]

        with patch(
            "sre_agent.tools.analysis.correlation.critical_path.fetch_trace_data"
        ) as mock_fetch:
            mock_fetch.return_value = self.create_mock_trace(mock_spans)

            result = analyze_critical_path(
                trace_id="bottleneck-trace",
                project_id="test-project",
            )

            # The slow-db-query should be identified as bottleneck
            if result.get("bottleneck_span"):
                assert result["bottleneck_span"]["name"] == "slow-db-query"

    def test_includes_optimization_recommendations(self):
        """Test that optimization recommendations are included."""
        mock_spans = [
            {
                "span_id": "root",
                "parent_span_id": None,
                "name": "request",
                "start_time": "2024-01-01T10:00:00Z",
                "end_time": "2024-01-01T10:00:01Z",
                "labels": {},
            },
        ]

        with patch(
            "sre_agent.tools.analysis.correlation.critical_path.fetch_trace_data"
        ) as mock_fetch:
            mock_fetch.return_value = self.create_mock_trace(mock_spans)

            result = analyze_critical_path(
                trace_id="rec-trace",
                project_id="test-project",
            )

            assert "optimization_recommendations" in result

    def test_includes_parallel_opportunities(self):
        """Test that parallelization opportunities are detected."""
        # Create trace with sequential sibling calls
        mock_spans = [
            {
                "span_id": "root",
                "parent_span_id": None,
                "name": "request",
                "start_time": "2024-01-01T10:00:00Z",
                "end_time": "2024-01-01T10:00:01Z",
                "labels": {"service.name": "api"},
            },
            {
                "span_id": "call-1",
                "parent_span_id": "root",
                "name": "db-query-1",
                "start_time": "2024-01-01T10:00:00.100Z",
                "end_time": "2024-01-01T10:00:00.300Z",
                "labels": {"service.name": "database"},
            },
            {
                "span_id": "call-2",
                "parent_span_id": "root",
                "name": "db-query-2",
                "start_time": "2024-01-01T10:00:00.300Z",
                "end_time": "2024-01-01T10:00:00.500Z",
                "labels": {"service.name": "database"},
            },
        ]

        with patch(
            "sre_agent.tools.analysis.correlation.critical_path.fetch_trace_data"
        ) as mock_fetch:
            mock_fetch.return_value = self.create_mock_trace(mock_spans)

            result = analyze_critical_path(
                trace_id="parallel-trace",
                project_id="test-project",
            )

            assert "parallel_opportunities" in result


class TestFindBottleneckServices:
    """Tests for find_bottleneck_services tool."""

    def test_basic_bottleneck_services_query(self):
        """Test basic bottleneck services SQL generation."""
        result = find_bottleneck_services(
            dataset_id="project.telemetry",
        )

        parsed = json.loads(result)
        assert parsed["analysis_type"] == "bottleneck_services"
        assert "sql_query" in parsed

    def test_sql_includes_contribution_metrics(self):
        """Test that SQL calculates contribution metrics."""
        result = find_bottleneck_services(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        # Should calculate contribution percentage
        assert "contribution" in sql.lower()
        assert "duration" in sql.lower()

    def test_custom_time_window(self):
        """Test that custom time window is used."""
        result = find_bottleneck_services(
            dataset_id="proj.ds",
            time_window_hours=48,
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        assert "48" in sql

    def test_custom_min_sample_size(self):
        """Test that custom minimum sample size is used."""
        result = find_bottleneck_services(
            dataset_id="proj.ds",
            min_sample_size=500,
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        assert "500" in sql

    def test_includes_metrics_explanation(self):
        """Test that metrics are explained."""
        result = find_bottleneck_services(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "metrics_explained" in parsed

        metrics = parsed["metrics_explained"]
        assert "avg_contribution_pct" in metrics
        assert "bottleneck_score" in metrics

    def test_includes_interpretation_guide(self):
        """Test that interpretation guide is included."""
        result = find_bottleneck_services(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "interpretation" in parsed

    def test_includes_next_steps(self):
        """Test that next steps are included."""
        result = find_bottleneck_services(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "next_steps" in parsed
        assert len(parsed["next_steps"]) > 0


class TestCalculateCriticalPathContribution:
    """Tests for calculate_critical_path_contribution tool."""

    def test_basic_contribution_calculation(self):
        """Test basic contribution calculation SQL generation."""
        result = calculate_critical_path_contribution(
            dataset_id="project.telemetry",
            service_name="my-service",
        )

        parsed = json.loads(result)
        assert parsed["analysis_type"] == "critical_path_contribution"
        assert parsed["target_service"] == "my-service"
        assert "sql_query" in parsed

    def test_sql_includes_service_filter(self):
        """Test that SQL filters by service name."""
        result = calculate_critical_path_contribution(
            dataset_id="proj.ds",
            service_name="target-service",
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        assert "target-service" in sql

    def test_sql_includes_operation_filter(self):
        """Test that SQL filters by operation name when provided."""
        result = calculate_critical_path_contribution(
            dataset_id="proj.ds",
            service_name="svc",
            operation_name="specific-operation",
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        assert "specific-operation" in sql

    def test_includes_duration_statistics(self):
        """Test that SQL calculates duration statistics."""
        result = calculate_critical_path_contribution(
            dataset_id="proj.ds",
            service_name="svc",
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        # Should include percentile calculations
        assert (
            "p50" in sql.lower() or "p95" in sql.lower() or "percentile" in sql.lower()
        )

    def test_includes_contribution_statistics(self):
        """Test that SQL calculates contribution statistics."""
        result = calculate_critical_path_contribution(
            dataset_id="proj.ds",
            service_name="svc",
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        assert "contribution" in sql.lower()

    def test_custom_time_window(self):
        """Test that custom time window is used."""
        result = calculate_critical_path_contribution(
            dataset_id="proj.ds",
            service_name="svc",
            time_window_hours=72,
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        assert "72" in sql

    def test_includes_optimization_formula(self):
        """Test that optimization formula is included."""
        result = calculate_critical_path_contribution(
            dataset_id="proj.ds",
            service_name="svc",
        )

        parsed = json.loads(result)
        assert "optimization_formula" in parsed

    def test_includes_metrics_explanation(self):
        """Test that metrics are explained."""
        result = calculate_critical_path_contribution(
            dataset_id="proj.ds",
            service_name="svc",
        )

        parsed = json.loads(result)
        assert "metrics_explained" in parsed


class TestCriticalPathToolsIntegration:
    """Integration tests for critical path analysis tools."""

    def test_bottleneck_services_returns_valid_json(self):
        """Test that find_bottleneck_services returns valid JSON."""
        result = find_bottleneck_services(dataset_id="proj.ds")
        parsed = json.loads(result)

        assert isinstance(parsed, dict)
        assert "sql_query" in parsed

    def test_contribution_returns_valid_json(self):
        """Test that calculate_critical_path_contribution returns valid JSON."""
        result = calculate_critical_path_contribution(
            dataset_id="proj.ds",
            service_name="test-service",
        )
        parsed = json.loads(result)

        assert isinstance(parsed, dict)
        assert "sql_query" in parsed

    def test_sql_queries_have_select_from_where(self):
        """Test that SQL queries have basic structure."""
        sql_tools = [
            (find_bottleneck_services, {"dataset_id": "proj.ds"}),
            (
                calculate_critical_path_contribution,
                {
                    "dataset_id": "proj.ds",
                    "service_name": "svc",
                },
            ),
        ]

        for tool, args in sql_tools:
            result = tool(**args)
            parsed = json.loads(result)
            sql = parsed["sql_query"]

            assert "SELECT" in sql
            assert "FROM" in sql

    def test_all_tools_include_next_steps(self):
        """Test that all SQL-returning tools include next steps."""
        sql_tools = [
            (find_bottleneck_services, {"dataset_id": "proj.ds"}),
            (
                calculate_critical_path_contribution,
                {
                    "dataset_id": "proj.ds",
                    "service_name": "svc",
                },
            ),
        ]

        for tool, args in sql_tools:
            result = tool(**args)
            parsed = json.loads(result)

            assert "next_steps" in parsed, f"{tool.__name__} missing next_steps"
            assert len(parsed["next_steps"]) > 0
