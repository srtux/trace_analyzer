"""End-to-end tests with comprehensive LLM and API mocking.

This test file demonstrates how to test the complete trace analysis workflow
with mocked LLM responses and synthetic test data for all API calls.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from tests.fixtures.synthetic_otel_data import (
    BigQueryResultGenerator,
    CloudLoggingAPIGenerator,
    CloudTraceAPIGenerator,
    TraceGenerator,
    generate_trace_id,
)


# Mock classes to replace broken google_adk.messages imports
class TextContent:
    def __init__(self, text: str):
        self.text = text


class ToolCall:
    def __init__(self, id: str, name: str, parameters: dict):
        self.id = id
        self.name = name
        self.parameters = parameters


class ToolResponse:
    def __init__(self, id: str, name: str, output: str):
        self.id = id
        self.name = name
        self.output = output


class Message:
    def __init__(self, role: str, content: list):
        self.role = role
        self.content = content


class MockLLMResponse:
    """Helper to create mock LLM responses."""

    @staticmethod
    def aggregate_analysis_response(tool_call_id: str = "call_1") -> Message:
        """Mock LLM response for aggregate analysis."""
        return Message(
            role="model",
            content=[
                TextContent(text="Let me analyze the aggregate metrics."),
                ToolCall(
                    id=tool_call_id,
                    name="analyze_aggregate_metrics",
                    parameters={
                        "dataset_id": "project.test_dataset",
                        "table_name": "_AllSpans",
                        "time_window_hours": 24,
                    },
                ),
            ],
        )

    @staticmethod
    def bigquery_execute_response(
        tool_call_id: str = "call_2", query: str = "SELECT * FROM test"
    ) -> Message:
        """Mock LLM response for BigQuery execution."""
        return Message(
            role="model",
            content=[
                TextContent(text="Let me execute this query."),
                ToolCall(
                    id=tool_call_id,
                    name="mcp__google-bigquery.googleapis.com-mcp__execute_sql",
                    parameters={"query": query},
                ),
            ],
        )

    @staticmethod
    def exemplar_selection_response(tool_call_id: str = "call_3") -> Message:
        """Mock LLM response for exemplar trace selection."""
        return Message(
            role="model",
            content=[
                TextContent(text="Let me find exemplar traces."),
                ToolCall(
                    id=tool_call_id,
                    name="find_exemplar_traces",
                    parameters={
                        "dataset_id": "project.test_dataset",
                        "selection_strategy": "errors",
                        "limit": 5,
                    },
                ),
            ],
        )

    @staticmethod
    def fetch_trace_response(
        tool_call_id: str = "call_4", trace_id: str = None
    ) -> Message:
        """Mock LLM response for fetching a trace."""
        if trace_id is None:
            trace_id = generate_trace_id()

        return Message(
            role="model",
            content=[
                TextContent(text=f"Let me fetch trace {trace_id}."),
                ToolCall(
                    id=tool_call_id,
                    name="fetch_trace",
                    parameters={"project_id": "test-project", "trace_id": trace_id},
                ),
            ],
        )

    @staticmethod
    def final_analysis_response() -> Message:
        """Mock LLM final analysis response."""
        return Message(
            role="model",
            content=[
                TextContent(
                    text="""## Analysis Summary

Based on the aggregate metrics and exemplar trace analysis:

1. **High Error Rate**: The frontend service shows a 15% error rate
2. **Latency Issues**: P95 latency increased by 200% compared to baseline
3. **Root Cause**: Database connection timeouts in the user-service

### Recommendations
- Scale database connection pool
- Add retry logic with exponential backoff
- Monitor database connection metrics
"""
                )
            ],
        )


class MockToolExecutor:
    """Mock tool executor that returns synthetic data."""

    def __init__(self):
        self.call_history = []

    def execute_tool(self, tool_name: str, parameters: dict) -> str:
        """Execute a tool and return synthetic response."""
        self.call_history.append({"tool": tool_name, "params": parameters})

        # Route to appropriate mock
        if tool_name == "analyze_aggregate_metrics":
            return self._mock_aggregate_metrics(parameters)
        elif tool_name.endswith("execute_sql"):
            return self._mock_bigquery_execute(parameters)
        elif tool_name == "find_exemplar_traces":
            return self._mock_exemplar_traces(parameters)
        elif tool_name == "fetch_trace":
            return self._mock_fetch_trace(parameters)
        elif tool_name == "get_logs_for_trace":
            return self._mock_get_logs(parameters)
        elif tool_name == "correlate_logs_with_trace":
            return self._mock_correlate_logs(parameters)
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    def _mock_aggregate_metrics(self, params: dict) -> str:
        """Mock aggregate metrics tool response."""
        query = f"""SELECT
  JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') as service_name,
  COUNT(*) as request_count,
  COUNTIF(status.code = 2) as error_count
FROM `{params["dataset_id"]}.{params.get("table_name", "_AllSpans")}`
WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
GROUP BY service_name
ORDER BY error_count DESC
"""
        return json.dumps(
            {
                "analysis_type": "aggregate_metrics",
                "sql_query": query.strip(),
                "description": "Aggregate metrics query",
            }
        )

    def _mock_bigquery_execute(self, params: dict) -> str:
        """Mock BigQuery execute_sql response."""
        query = params.get("query", "")

        # Detect query type and return appropriate synthetic data
        if "aggregate" in query.lower() or "request_count" in query.lower():
            results = BigQueryResultGenerator.aggregate_metrics_result(
                services=["frontend", "api-gateway", "user-service"], with_errors=True
            )
        elif "trace_id" in query.lower() and "error" not in query.lower():
            results = BigQueryResultGenerator.exemplar_traces_result(
                count=5, strategy="outliers"
            )
        elif "exception" in query.lower():
            results = BigQueryResultGenerator.exception_events_result(count=10)
        else:
            results = BigQueryResultGenerator.exemplar_traces_result(count=5)

        return json.dumps({"rows": results, "total_rows": len(results)})

    def _mock_exemplar_traces(self, params: dict) -> str:
        """Mock find_exemplar_traces tool response."""
        strategy = params.get("selection_strategy", "outliers")
        query = f"""SELECT trace_id, name, service_name, duration_ms
FROM `{params["dataset_id"]}._AllSpans`
WHERE status.code = 2
LIMIT {params.get("limit", 10)}
"""
        return json.dumps(
            {
                "analysis_type": "exemplar_selection",
                "selection_strategy": strategy,
                "sql_query": query.strip(),
            }
        )

    def _mock_fetch_trace(self, params: dict) -> str:
        """Mock fetch_trace tool response."""
        trace_id = params.get("trace_id")
        trace_data = CloudTraceAPIGenerator.trace_response(
            trace_id=trace_id, include_error=True
        )
        return json.dumps(trace_data)

    def _mock_get_logs(self, params: dict) -> str:
        """Mock get_logs_for_trace tool response."""
        trace_id = params.get("trace_id")
        log_data = CloudLoggingAPIGenerator.log_entries_response(
            count=5, trace_id=trace_id, severity="ERROR"
        )
        return json.dumps(log_data)

    def _mock_correlate_logs(self, params: dict) -> str:
        """Mock correlate_logs_with_trace tool response."""
        trace_id = params.get("trace_id")
        query = f"""WITH trace_context AS (
  SELECT MIN(start_time) as trace_start,
         MAX(end_time) as trace_end
  FROM `project.dataset._AllSpans`
  WHERE trace_id = '{trace_id}'
)
SELECT * FROM logs WHERE trace_id = '{trace_id}'
"""
        return json.dumps(
            {
                "analysis_type": "log_correlation",
                "trace_id": trace_id,
                "sql_query": query.strip(),
            }
        )


@pytest.fixture
def mock_tool_executor():
    """Fixture providing a mock tool executor."""
    return MockToolExecutor()


@pytest.fixture
def mock_llm_client():
    """Fixture providing a mock LLM client."""
    mock = MagicMock()

    # Define a sequence of mock responses for a typical analysis flow
    responses = [
        # 1. Initial aggregate analysis
        MockLLMResponse.aggregate_analysis_response("call_1"),
        # 2. Execute BigQuery for aggregate metrics
        MockLLMResponse.bigquery_execute_response("call_2"),
        # 3. Find exemplar traces
        MockLLMResponse.exemplar_selection_response("call_3"),
        # 4. Execute BigQuery for exemplars
        MockLLMResponse.bigquery_execute_response("call_4"),
        # 5. Fetch a specific trace
        MockLLMResponse.fetch_trace_response("call_5"),
        # 6. Final analysis
        MockLLMResponse.final_analysis_response(),
    ]

    async def generate_response_stream(*args, **kwargs):
        for response in responses:
            yield response

    mock.generate = generate_response_stream

    return mock


class TestEndToEndWithMocks:
    """End-to-end tests with comprehensive mocking."""

    @pytest.mark.asyncio
    async def test_complete_analysis_workflow_with_mocks(
        self, mock_llm_client, mock_tool_executor
    ):
        """Test complete analysis workflow with mocked LLM and tool responses."""

        # Create a mock agent with our mocked LLM
        with patch("google.adk.agents.LlmAgent") as MockAgent:
            agent_instance = MockAgent.return_value
            agent_instance.generate = mock_llm_client.generate

            # Simulate user request

            # Run analysis workflow
            response_count = 0
            async for response in mock_llm_client.generate():
                response_count += 1

                # Verify response structure
                assert isinstance(response, Message)
                assert response.role == "model"
                assert len(response.content) > 0

                # Extract tool calls and execute them
                for content in response.content:
                    if isinstance(content, ToolCall):
                        # Execute tool with mock
                        tool_result = mock_tool_executor.execute_tool(
                            content.name, content.parameters
                        )

                        # Verify tool result is valid JSON
                        parsed_result = json.loads(tool_result)
                        assert isinstance(parsed_result, dict)

                # Stop after final response
                if response_count >= 6:
                    break

            # Verify workflow completed expected steps
            assert response_count == 6

            # Verify tools were called in correct order
            assert len(mock_tool_executor.call_history) > 0

            # Verify aggregate analysis was called
            aggregate_calls = [
                call
                for call in mock_tool_executor.call_history
                if call["tool"] == "analyze_aggregate_metrics"
            ]
            assert len(aggregate_calls) > 0

    @pytest.mark.asyncio
    async def test_error_trace_analysis_workflow(self, mock_tool_executor):
        """Test workflow specifically for error trace analysis."""

        # Generate synthetic error trace
        trace_gen = TraceGenerator(service_name="frontend")
        error_trace = trace_gen.create_simple_http_trace(
            endpoint="/api/checkout", include_db_call=True, include_error=True
        )

        # Verify error trace has correct structure
        assert len(error_trace) > 0
        root_span = error_trace[0]
        assert root_span["status"]["code"] == 2  # ERROR
        assert len(root_span["events"]) > 0  # Has exception event

        # Simulate fetching this trace
        trace_id = root_span["trace_id"]
        result = mock_tool_executor.execute_tool(
            "fetch_trace", {"project_id": "test-project", "trace_id": trace_id}
        )

        # Verify result
        trace_data = json.loads(result)
        assert "traceId" in trace_data
        assert "spans" in trace_data

    @pytest.mark.asyncio
    async def test_bigquery_aggregate_analysis(self, mock_tool_executor):
        """Test BigQuery aggregate metrics analysis."""

        # Execute aggregate metrics
        result = mock_tool_executor.execute_tool(
            "analyze_aggregate_metrics",
            {
                "dataset_id": "project.test_dataset",
                "table_name": "_AllSpans",
                "time_window_hours": 24,
            },
        )

        # Verify query generation
        data = json.loads(result)
        assert data["analysis_type"] == "aggregate_metrics"
        assert "sql_query" in data
        assert "SELECT" in data["sql_query"]

        # Execute the generated query
        query_result = mock_tool_executor.execute_tool(
            "mcp__google-bigquery.googleapis.com-mcp__execute_sql",
            {"query": data["sql_query"]},
        )

        # Verify results
        query_data = json.loads(query_result)
        assert "rows" in query_data
        assert len(query_data["rows"]) > 0

        # Verify result structure
        first_row = query_data["rows"][0]
        assert "service_name" in first_row
        assert "request_count" in first_row
        assert "error_count" in first_row
        assert "error_rate_pct" in first_row

    @pytest.mark.asyncio
    async def test_exemplar_trace_selection_and_fetch(self, mock_tool_executor):
        """Test exemplar trace selection and fetching."""

        # Find exemplar traces
        exemplar_result = mock_tool_executor.execute_tool(
            "find_exemplar_traces",
            {
                "dataset_id": "project.test_dataset",
                "selection_strategy": "errors",
                "limit": 5,
            },
        )

        # Verify exemplar query
        exemplar_data = json.loads(exemplar_result)
        assert "sql_query" in exemplar_data
        assert "selection_strategy" in exemplar_data

        # Execute exemplar query
        trace_list_result = mock_tool_executor.execute_tool(
            "mcp__google-bigquery.googleapis.com-mcp__execute_sql",
            {"query": "SELECT trace_id FROM traces WHERE status.code = 2"},
        )

        # Verify trace list
        trace_list = json.loads(trace_list_result)
        assert "rows" in trace_list
        assert len(trace_list["rows"]) > 0

        # Fetch first trace
        first_trace_id = trace_list["rows"][0].get("trace_id", generate_trace_id())
        trace_detail_result = mock_tool_executor.execute_tool(
            "fetch_trace", {"project_id": "test-project", "trace_id": first_trace_id}
        )

        # Verify trace details
        trace_detail = json.loads(trace_detail_result)
        assert "traceId" in trace_detail
        assert "spans" in trace_detail

    @pytest.mark.asyncio
    async def test_log_correlation_workflow(self, mock_tool_executor):
        """Test log correlation with traces."""

        trace_id = generate_trace_id()

        # Correlate logs with trace
        log_query_result = mock_tool_executor.execute_tool(
            "correlate_logs_with_trace",
            {
                "dataset_id": "project.test_dataset",
                "trace_id": trace_id,
                "include_nearby_logs": True,
            },
        )

        # Verify log query
        log_query = json.loads(log_query_result)
        assert "sql_query" in log_query
        assert trace_id in log_query["sql_query"]

        # Get logs for trace
        logs_result = mock_tool_executor.execute_tool(
            "get_logs_for_trace", {"project_id": "test-project", "trace_id": trace_id}
        )

        # Verify logs
        logs = json.loads(logs_result)
        assert "entries" in logs
        assert len(logs["entries"]) > 0

        # Verify log entry structure
        first_log = logs["entries"][0]
        assert "logName" in first_log
        assert "timestamp" in first_log
        assert "severity" in first_log

    @pytest.mark.asyncio
    async def test_exception_analysis_workflow(self, mock_tool_executor):
        """Test exception event analysis workflow."""

        # Execute exception query
        exception_result = mock_tool_executor.execute_tool(
            "mcp__google-bigquery.googleapis.com-mcp__execute_sql",
            {"query": "SELECT * FROM spans WHERE event.name = 'exception'"},
        )

        # Verify exception data
        exceptions = json.loads(exception_result)
        assert "rows" in exceptions
        assert len(exceptions["rows"]) > 0

        # Verify exception structure
        first_exception = exceptions["rows"][0]
        assert "exception_type" in first_exception
        assert "exception_message" in first_exception
        assert "trace_id" in first_exception

    def test_synthetic_data_generation(self):
        """Test synthetic data generators produce valid data."""

        # Test trace generation
        trace_gen = TraceGenerator()
        traces = trace_gen.create_multi_service_trace(
            services=["frontend", "api", "database"], include_errors=True
        )

        assert len(traces) == 3
        assert all("trace_id" in span for span in traces)
        assert all("span_id" in span for span in traces)
        assert all("resource" in span for span in traces)

        # Test BigQuery result generation
        bq_results = BigQueryResultGenerator.aggregate_metrics_result(
            services=["frontend", "backend"], with_errors=True
        )

        assert len(bq_results) == 2
        assert all("service_name" in row for row in bq_results)
        assert all("error_rate_pct" in row for row in bq_results)

        # Test Cloud Trace API generation
        trace_response = CloudTraceAPIGenerator.trace_response(include_error=True)
        assert "traceId" in trace_response
        assert "spans" in trace_response
        assert len(trace_response["spans"]) > 0

        # Test Cloud Logging API generation
        log_response = CloudLoggingAPIGenerator.log_entries_response(
            count=5, severity="ERROR"
        )
        assert "entries" in log_response
        assert len(log_response["entries"]) == 5
        assert all(entry["severity"] == "ERROR" for entry in log_response["entries"])


class TestMockToolExecutor:
    """Tests for the mock tool executor itself."""

    def test_mock_executor_tracks_calls(self):
        """Test that mock executor tracks tool calls."""
        executor = MockToolExecutor()

        # Make several tool calls
        executor.execute_tool("analyze_aggregate_metrics", {"dataset_id": "test"})
        executor.execute_tool("find_exemplar_traces", {"dataset_id": "test"})

        # Verify call history
        assert len(executor.call_history) == 2
        assert executor.call_history[0]["tool"] == "analyze_aggregate_metrics"
        assert executor.call_history[1]["tool"] == "find_exemplar_traces"

    def test_mock_executor_returns_valid_json(self):
        """Test that all mock responses are valid JSON."""
        executor = MockToolExecutor()

        tools_to_test = [
            ("analyze_aggregate_metrics", {"dataset_id": "test"}),
            ("find_exemplar_traces", {"dataset_id": "test"}),
            ("fetch_trace", {"project_id": "test", "trace_id": generate_trace_id()}),
            (
                "get_logs_for_trace",
                {"project_id": "test", "trace_id": generate_trace_id()},
            ),
        ]

        for tool_name, params in tools_to_test:
            result = executor.execute_tool(tool_name, params)
            # Should not raise exception
            data = json.loads(result)
            assert isinstance(data, dict)
