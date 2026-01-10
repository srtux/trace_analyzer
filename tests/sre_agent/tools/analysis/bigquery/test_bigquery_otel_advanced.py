"""Tests for advanced BigQuery OTel analysis tools."""

import json

from sre_agent.tools.analysis.bigquery import otel_advanced as bigquery_otel_advanced


class TestAnalyzeSpanEvents:
    """Tests for analyze_span_events tool."""

    def test_basic_event_analysis(self):
        """Test basic span event analysis query."""
        result = bigquery_otel_advanced.analyze_span_events(
            dataset_id="project.dataset"
        )

        data = json.loads(result)
        assert data["analysis_type"] == "span_events"
        query = data["sql_query"]
        assert "UNNEST(events)" in query
        assert "event.name" in query
        assert "event.time" in query
        assert "ARRAY_LENGTH(events) > 0" in query

    def test_event_analysis_with_filter(self):
        """Test event analysis with event name filter."""
        result = bigquery_otel_advanced.analyze_span_events(
            dataset_id="project.dataset", event_name_filter="exception"
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "event.name = 'exception'" in query

    def test_event_analysis_extracts_exception_fields(self):
        """Test that query extracts exception-specific fields."""
        result = bigquery_otel_advanced.analyze_span_events(
            dataset_id="project.dataset"
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "exception.type" in query
        assert "exception.message" in query
        assert "exception.stacktrace" in query


class TestAnalyzeExceptionPatterns:
    """Tests for analyze_exception_patterns tool."""

    def test_exception_pattern_by_type(self):
        """Test exception pattern analysis grouped by type."""
        result = bigquery_otel_advanced.analyze_exception_patterns(
            dataset_id="project.dataset", group_by="exception_type"
        )

        data = json.loads(result)
        assert data["analysis_type"] == "exception_patterns"
        query = data["sql_query"]
        assert "event.name = 'exception'" in query
        assert "exception.type" in query
        assert "GROUP BY" in query

    def test_exception_pattern_by_service(self):
        """Test exception pattern analysis grouped by service."""
        result = bigquery_otel_advanced.analyze_exception_patterns(
            dataset_id="project.dataset", group_by="service_name"
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "service_name" in query

    def test_exception_pattern_includes_aggregates(self):
        """Test that exception patterns include aggregate data."""
        result = bigquery_otel_advanced.analyze_exception_patterns(
            dataset_id="project.dataset"
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "exception_count" in query
        assert "affected_traces" in query
        assert "affected_services" in query
        assert "sample_messages" in query


class TestAnalyzeSpanLinks:
    """Tests for analyze_span_links tool."""

    def test_basic_link_analysis(self):
        """Test basic span link analysis query."""
        result = bigquery_otel_advanced.analyze_span_links(dataset_id="project.dataset")

        data = json.loads(result)
        assert data["analysis_type"] == "span_links"
        query = data["sql_query"]
        assert "UNNEST(links)" in query
        assert "link.trace_id" in query
        assert "link.span_id" in query
        assert "ARRAY_LENGTH(links) > 0" in query

    def test_link_analysis_extracts_link_attributes(self):
        """Test that query extracts link-specific attributes."""
        result = bigquery_otel_advanced.analyze_span_links(dataset_id="project.dataset")

        data = json.loads(result)
        query = data["sql_query"]
        assert "link.type" in query
        assert "link.reason" in query
        assert "link.attributes" in query

    def test_link_analysis_with_service_filter(self):
        """Test link analysis with service filter."""
        result = bigquery_otel_advanced.analyze_span_links(
            dataset_id="project.dataset", service_name="frontend"
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert (
            "JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') = 'frontend'"
            in query
        )


class TestAnalyzeLinkPatterns:
    """Tests for analyze_link_patterns tool."""

    def test_link_pattern_aggregation(self):
        """Test link pattern aggregation query."""
        result = bigquery_otel_advanced.analyze_link_patterns(
            dataset_id="project.dataset"
        )

        data = json.loads(result)
        assert data["analysis_type"] == "link_patterns"
        query = data["sql_query"]
        assert "spans_with_links" in query
        assert "total_links" in query
        assert "avg_links_per_span" in query
        assert "ARRAY_LENGTH(links)" in query


class TestAnalyzeInstrumentationLibraries:
    """Tests for analyze_instrumentation_libraries tool."""

    def test_basic_instrumentation_analysis(self):
        """Test basic instrumentation library analysis."""
        result = bigquery_otel_advanced.analyze_instrumentation_libraries(
            dataset_id="project.dataset"
        )

        data = json.loads(result)
        assert data["analysis_type"] == "instrumentation_libraries"
        query = data["sql_query"]
        assert "instrumentation_scope.name" in query
        assert "instrumentation_scope.version" in query
        assert "instrumentation_scope.schema_url" in query

    def test_instrumentation_includes_aggregates(self):
        """Test that instrumentation analysis includes aggregates."""
        result = bigquery_otel_advanced.analyze_instrumentation_libraries(
            dataset_id="project.dataset"
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "span_count" in query
        assert "service_count" in query
        assert "trace_count" in query
        assert "services_using" in query


class TestAnalyzeHTTPAttributes:
    """Tests for analyze_http_attributes tool."""

    def test_basic_http_analysis(self):
        """Test basic HTTP attribute analysis."""
        result = bigquery_otel_advanced.analyze_http_attributes(
            dataset_id="project.dataset"
        )

        data = json.loads(result)
        assert data["analysis_type"] == "http_attributes"
        query = data["sql_query"]
        assert "kind = 2" in query  # SERVER spans
        assert "http.method" in query
        assert "http.target" in query
        assert "http.status_code" in query

    def test_http_analysis_includes_latency(self):
        """Test that HTTP analysis includes latency metrics."""
        result = bigquery_otel_advanced.analyze_http_attributes(
            dataset_id="project.dataset"
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "p50_ms" in query
        assert "p95_ms" in query
        assert "p99_ms" in query

    def test_http_analysis_includes_request_size(self):
        """Test that HTTP analysis includes request/response sizes."""
        result = bigquery_otel_advanced.analyze_http_attributes(
            dataset_id="project.dataset"
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "http.request_content_length" in query
        assert "http.response_content_length" in query

    def test_http_analysis_with_min_requests(self):
        """Test HTTP analysis with minimum request filter."""
        result = bigquery_otel_advanced.analyze_http_attributes(
            dataset_id="project.dataset", min_request_count=50
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "HAVING request_count >= 50" in query


class TestAnalyzeDatabaseOperations:
    """Tests for analyze_database_operations tool."""

    def test_basic_database_analysis(self):
        """Test basic database operation analysis."""
        result = bigquery_otel_advanced.analyze_database_operations(
            dataset_id="project.dataset"
        )

        data = json.loads(result)
        assert data["analysis_type"] == "database_operations"
        query = data["sql_query"]
        assert "kind = 3" in query  # CLIENT spans
        assert "db.system" in query
        assert "db.name" in query
        assert "db.operation" in query

    def test_database_analysis_with_db_system_filter(self):
        """Test database analysis with database system filter."""
        result = bigquery_otel_advanced.analyze_database_operations(
            dataset_id="project.dataset", db_system="postgresql"
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "db.system') = 'postgresql'" in query

    def test_database_analysis_includes_sample_statements(self):
        """Test that database analysis includes sample SQL statements."""
        result = bigquery_otel_advanced.analyze_database_operations(
            dataset_id="project.dataset"
        )

        data = json.loads(result)
        query = data["sql_query"]
        assert "db.statement" in query
        assert "sample_statements" in query


class TestAdvancedToolsIntegration:
    """Integration tests for advanced tools."""

    def test_all_tools_return_valid_json(self):
        """Test that all advanced tools return valid JSON."""
        tools = [
            bigquery_otel_advanced.analyze_span_events,
            bigquery_otel_advanced.analyze_exception_patterns,
            bigquery_otel_advanced.analyze_span_links,
            bigquery_otel_advanced.analyze_link_patterns,
            bigquery_otel_advanced.analyze_instrumentation_libraries,
            bigquery_otel_advanced.analyze_http_attributes,
            bigquery_otel_advanced.analyze_database_operations,
        ]

        for tool in tools:
            result = tool(dataset_id="project.dataset")
            data = json.loads(result)
            assert isinstance(data, dict)
            assert "analysis_type" in data
            assert "sql_query" in data

    def test_all_queries_use_correct_table_name(self):
        """Test that all queries use _AllSpans table by default."""
        tools = [
            bigquery_otel_advanced.analyze_span_events,
            bigquery_otel_advanced.analyze_exception_patterns,
            bigquery_otel_advanced.analyze_span_links,
            bigquery_otel_advanced.analyze_link_patterns,
            bigquery_otel_advanced.analyze_instrumentation_libraries,
            bigquery_otel_advanced.analyze_http_attributes,
            bigquery_otel_advanced.analyze_database_operations,
        ]

        for tool in tools:
            result = tool(dataset_id="project.dataset")
            data = json.loads(result)
            query = data["sql_query"]
            assert "_AllSpans" in query

    def test_all_queries_have_time_filters(self):
        """Test that all queries include time window filters."""
        tools = [
            bigquery_otel_advanced.analyze_span_events,
            bigquery_otel_advanced.analyze_exception_patterns,
            bigquery_otel_advanced.analyze_span_links,
            bigquery_otel_advanced.analyze_link_patterns,
            bigquery_otel_advanced.analyze_instrumentation_libraries,
            bigquery_otel_advanced.analyze_http_attributes,
            bigquery_otel_advanced.analyze_database_operations,
        ]

        for tool in tools:
            result = tool(dataset_id="project.dataset", time_window_hours=24)
            data = json.loads(result)
            query = data["sql_query"]
            assert "start_time >=" in query or "INTERVAL" in query
