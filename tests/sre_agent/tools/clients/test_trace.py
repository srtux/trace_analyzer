import json
from unittest.mock import MagicMock, patch

import pytest
from google.cloud import logging_v2, trace_v1

import sre_agent.tools.clients.trace as trace_client
from sre_agent.tools.clients.logging import list_error_events, list_log_entries
from tests.fixtures.synthetic_otel_data import (
    CloudLoggingAPIGenerator,
    CloudTraceAPIGenerator,
    generate_trace_id,
)


@pytest.fixture
def mock_trace_client():
    """Mock Cloud Trace API client."""
    mock_client = MagicMock(spec=trace_v1.TraceServiceClient)
    return mock_client


@pytest.fixture
def mock_logging_client():
    """Mock Cloud Logging API client."""
    mock_client = MagicMock(spec=logging_v2.LoggingServiceV2Client)
    return mock_client


class TestFetchTrace:
    """Tests for fetch_trace function."""

    @pytest.mark.asyncio
    @patch("sre_agent.tools.clients.trace.get_trace_client")
    async def test_fetch_trace_success(self, mock_get_client):
        """Test successful trace fetch."""
        # Setup mock
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        trace_id = generate_trace_id()

        # Convert to mock Trace object
        mock_trace = MagicMock()
        mock_trace.trace_id = trace_id
        mock_trace.project_id = "test-project"
        mock_trace.spans = []

        mock_client.get_trace.return_value = mock_trace

        # Execute
        result_json = await trace_client.fetch_trace(
            project_id="test-project", trace_id=trace_id
        )

        # Verify
        assert result_json is not None
        result = json.loads(result_json)
        assert result["trace_id"] == trace_id
        mock_client.get_trace.assert_called_once()

    @pytest.mark.asyncio
    @patch("sre_agent.tools.clients.trace.get_trace_client")
    async def test_fetch_trace_with_invalid_trace_id(self, mock_get_client):
        """Test fetch trace with invalid trace ID."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Setup mock to raise exception
        from google.api_core import exceptions

        mock_client.get_trace.side_effect = exceptions.NotFound("Trace not found")

        # Execute
        result_json = await trace_client.fetch_trace(
            project_id="test-project", trace_id="invalid-trace-id"
        )

        # Verify error handling (it returns an error JSON, not raises)
        result = json.loads(result_json)
        assert "error" in result
        assert "404" in result["error"]


class TestListTraces:
    """Tests for list_traces function."""

    @pytest.mark.asyncio
    @patch("sre_agent.tools.clients.trace.get_trace_client")
    async def test_list_traces_success(self, mock_get_client):
        """Test successful trace listing."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Setup mock response
        mock_traces = []
        for _i in range(5):
            mock_trace = MagicMock()
            mock_trace.trace_id = generate_trace_id()
            mock_trace.project_id = "test-project"
            mock_trace.spans = []  # Needed for duration calc
            mock_traces.append(mock_trace)

        mock_client.list_traces.return_value = mock_traces

        # Execute
        result_json = await trace_client.list_traces(
            project_id="test-project", limit=10
        )

        # Verify
        assert result_json is not None
        result = json.loads(result_json)
        assert len(result) <= 5
        mock_client.list_traces.assert_called_once()

    @pytest.mark.asyncio
    @patch("sre_agent.tools.clients.trace.get_trace_client")
    async def test_list_traces_with_time_filter(self, mock_get_client):
        """Test trace listing with time filter."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.list_traces.return_value = []

        # Execute with time filter
        await trace_client.list_traces(
            project_id="test-project",
            start_time="2024-01-01T00:00:00Z",
            end_time="2024-01-02T00:00:00Z",
        )

        # Verify filter was applied
        call_args = mock_client.list_traces.call_args
        assert call_args is not None


class TestGetLogsForTrace:
    """Tests for get_logs_for_trace function."""

    @pytest.mark.asyncio
    @patch("sre_agent.tools.clients.logging.get_logging_client")
    async def test_get_logs_for_trace_success(self, mock_get_client):
        """Test successful log retrieval for trace."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        trace_id = generate_trace_id()
        mock_logs = CloudLoggingAPIGenerator.log_entries_response(
            count=5, trace_id=trace_id, severity="ERROR"
        )

        # Setup mock response
        mock_entries = []
        for log_entry in mock_logs["entries"]:
            mock_entry = MagicMock()
            mock_entry.text_payload = log_entry["textPayload"]
            mock_entry.json_payload = None
            mock_entry.proto_payload = None
            mock_entry.insert_id = "test-id"
            mock_entry.severity = MagicMock()
            mock_entry.severity.name = log_entry["severity"]
            mock_entry.timestamp = MagicMock()
            mock_entry.timestamp.isoformat.return_value = log_entry["timestamp"]
            mock_entry.resource = MagicMock()
            mock_entry.resource.type = "global"
            mock_entry.resource.labels = {}
            mock_entries.append(mock_entry)

        mock_pager = MagicMock()
        mock_page = MagicMock()
        mock_page.entries = mock_entries
        mock_page.__iter__.return_value = iter(mock_entries)
        mock_page.next_page_token = None
        mock_pager.pages = iter([mock_page])
        mock_client.list_log_entries.return_value = mock_pager

        # Execute
        result_json = await list_log_entries(
            project_id="test-project",
            filter_str=f'trace="projects/test-project/traces/{trace_id}"',
        )

        # Verify
        assert result_json is not None
        result = json.loads(result_json)
        assert len(result["entries"]) == 5
        mock_client.list_log_entries.assert_called_once()


class TestFindExampleTraces:
    """Tests for find_example_traces function."""

    @pytest.mark.asyncio
    @patch("sre_agent.tools.clients.trace.get_trace_client")
    async def test_find_example_traces_with_error_filter(self, mock_get_client):
        """Test finding example traces with error filter."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Setup mock traces with errors
        mock_traces = []
        for _i in range(3):
            mock_trace = MagicMock()
            mock_trace.trace_id = generate_trace_id()
            mock_trace.project_id = "test-project"
            # Give them some span to avoid duration errors
            mock_span = MagicMock()
            mock_span.name = "root"
            mock_span.start_time.timestamp.return_value = 1000
            mock_span.start_time.isoformat.return_value = "2024-01-01T00:00:00Z"
            mock_span.end_time.timestamp.return_value = 2000
            mock_span.labels = {}
            mock_trace.spans = [mock_span]
            mock_traces.append(mock_trace)

        mock_client.list_traces.return_value = mock_traces

        # Execute
        result_json = await trace_client.find_example_traces(
            project_id="test-project", prefer_errors=True
        )

        # Verify
        assert result_json is not None
        result = json.loads(result_json)
        assert "baseline" in result
        assert "anomaly" in result
        mock_client.list_traces.assert_called()


class TestGetTraceByURL:
    """Tests for get_trace_by_url function."""

    @pytest.mark.asyncio
    async def test_extract_trace_id_from_url(self):
        """Test extracting trace ID from Cloud Console URL."""
        # Use a long enough hex string to satisfy the fallback parser if needed,
        # but here we test the 'trace-details' part.
        url = "https://console.cloud.google.com/traces/trace-details/4fb09ce68979116e0ca143d225695000?project=test-project"

        # Mock the actual fetch to focus on URL parsing
        with patch("sre_agent.tools.clients.trace.fetch_trace") as mock_fetch:
            mock_fetch.return_value = json.dumps(
                {"trace_id": "4fb09ce68979116e0ca143d225695000"}
            )

            await trace_client.get_trace_by_url(url)

            # Verify trace was fetched with correct ID
            mock_fetch.assert_called_once()
            args, _kwargs = mock_fetch.call_args
            assert args[1] == "4fb09ce68979116e0ca143d225695000"

    @pytest.mark.asyncio
    async def test_get_trace_by_url_invalid_url(self):
        """Test handling of invalid URL."""
        invalid_url = "https://example.com/invalid"

        result_json = await trace_client.get_trace_by_url(invalid_url)
        result = json.loads(result_json)
        assert "error" in result


class TestListErrorEvents:
    """Tests for list_error_events function."""

    @pytest.mark.asyncio
    @patch("google.cloud.errorreporting_v1beta1.ErrorStatsServiceClient")
    async def test_list_error_events_success(self, mock_client_class):
        """Test successful error event listing."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Setup mock error events
        mock_events = []
        for i in range(5):
            mock_event = MagicMock()
            mock_event.message = f"Error message {i}"
            mock_event.event_time.isoformat.return_value = "2024-01-01T00:00:00Z"
            mock_event.service_context.service = "test-service"
            mock_event.service_context.version = "1.0"
            mock_events.append(mock_event)

        mock_client.list_events.return_value = mock_events

        # Execute
        result_json = await list_error_events(project_id="test-project", minutes_ago=60)

        # Verify
        assert result_json is not None
        result = json.loads(result_json)
        assert len(result) == 5
        mock_client.list_events.assert_called_once()


class TestListLogEntries:
    """Tests for list_log_entries function."""

    @pytest.mark.asyncio
    @patch("sre_agent.tools.clients.logging.get_logging_client")
    async def test_list_log_entries_success(self, mock_get_client):
        """Test successful log entry listing."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Setup mock log entries
        mock_logs = CloudLoggingAPIGenerator.log_entries_response(
            count=10, severity="ERROR"
        )

        mock_entries = []
        for log_entry in mock_logs["entries"]:
            mock_entry = MagicMock()
            mock_entry.text_payload = log_entry["textPayload"]
            mock_entry.json_payload = None
            mock_entry.proto_payload = None
            mock_entry.insert_id = "test-id"
            mock_entry.severity.name = log_entry["severity"]
            mock_entry.timestamp.isoformat.return_value = log_entry["timestamp"]
            mock_entry.resource.type = "global"
            mock_entry.resource.labels = {}
            mock_entries.append(mock_entry)

        mock_pager = MagicMock()
        mock_page = MagicMock()
        mock_page.entries = mock_entries
        mock_page.__iter__.return_value = iter(mock_entries)
        mock_page.next_page_token = None
        mock_pager.pages = iter([mock_page])
        mock_client.list_log_entries.return_value = mock_pager

        # Execute
        result_json = await list_log_entries(
            project_id="test-project", filter_str='severity="ERROR"', limit=10
        )

        # Verify
        assert result_json is not None
        result = json.loads(result_json)
        assert len(result["entries"]) == 10
        mock_client.list_log_entries.assert_called_once()


class TestIntegration:
    """Integration tests for trace client tools."""

    @pytest.mark.asyncio
    @patch("sre_agent.tools.clients.trace.get_trace_client")
    @patch("sre_agent.tools.clients.logging.get_logging_client")
    async def test_fetch_trace_and_logs_workflow(
        self, mock_get_logging, mock_get_trace
    ):
        """Test complete workflow of fetching trace and its logs."""
        # Setup trace mock
        trace_id = generate_trace_id()
        mock_trace = MagicMock()
        mock_trace.trace_id = trace_id
        mock_trace.project_id = "test-project"
        mock_trace.project_id = "test-project"
        mock_trace.spans = []

        mock_get_trace.return_value.get_trace.return_value = mock_trace

        # Setup logging mock
        mock_log_entry = MagicMock()
        mock_log_entry.text_payload = "Error occurred"
        mock_log_entry.json_payload = None
        mock_log_entry.proto_payload = None
        mock_log_entry.insert_id = "test-id"
        mock_log_entry.severity.name = "ERROR"
        mock_log_entry.timestamp.isoformat.return_value = "2024-01-01T00:00:00Z"
        mock_log_entry.resource.type = "global"
        mock_log_entry.resource.labels = {}

        mock_pager = MagicMock()
        mock_page = MagicMock()
        mock_page.entries = [mock_log_entry]
        mock_page.__iter__.return_value = iter([mock_log_entry])
        mock_page.next_page_token = None
        mock_pager.pages = iter([mock_page])
        mock_get_logging.return_value.list_log_entries.return_value = mock_pager

        # Execute workflow
        trace_result = await trace_client.fetch_trace(
            project_id="test-project", trace_id=trace_id
        )

        log_result = await list_log_entries(
            project_id="test-project",
            filter_str=f'trace="projects/test-project/traces/{trace_id}"',
        )

        # Verify both calls succeeded
        assert trace_result is not None
        assert log_result is not None

    def test_synthetic_data_matches_api_structure(self):
        """Test that synthetic data matches actual API structure."""
        # Generate synthetic trace
        trace_data = CloudTraceAPIGenerator.trace_response(include_error=True)

        # Verify structure matches Cloud Trace API
        assert "projectId" in trace_data
        assert "traceId" in trace_data
        assert "spans" in trace_data
        assert isinstance(trace_data["spans"], list)

        if len(trace_data["spans"]) > 0:
            span = trace_data["spans"][0]
            assert "spanId" in span
            assert "name" in span
            assert "startTime" in span

        # Generate synthetic logs
        log_data = CloudLoggingAPIGenerator.log_entries_response(count=5)

        # Verify structure matches Cloud Logging API
        assert "entries" in log_data
        assert isinstance(log_data["entries"], list)
        assert len(log_data["entries"]) == 5

        if len(log_data["entries"]) > 0:
            entry = log_data["entries"][0]
            assert "logName" in entry
            assert "timestamp" in entry
            assert "severity" in entry


def test_fetch_trace_data_uses_sync_impl():
    """Verify that fetch_trace_data uses the synchronous implementation."""
    from sre_agent.tools.clients.trace import fetch_trace_data

    with patch(
        "sre_agent.tools.clients.trace._fetch_trace_sync", return_value="{}"
    ) as mock_sync:
        fetch_trace_data("12345", "test-project")
        mock_sync.assert_called_once_with("test-project", "12345")
