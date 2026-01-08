import json
import os
from unittest import mock

import pytest

from trace_analyzer.tools.o11y_clients import (
    _get_project_id,
    fetch_trace,
    find_example_traces,
    get_trace_by_url,
    list_traces,
)


@pytest.fixture
def mock_trace_service_client():
    with mock.patch(
        "trace_analyzer.tools.o11y_clients.trace_v1.TraceServiceClient"
    ) as mock_client:
        yield mock_client


@pytest.fixture
def mock_env_vars():
    with mock.patch.dict(os.environ, {"TRACE_PROJECT_ID": "test-project"}, clear=True):
        yield


def test_get_project_id_from_trace_project_id(mock_env_vars):
    assert _get_project_id() == "test-project"


def test_get_project_id_from_google_cloud_project():
    with mock.patch.dict(
        os.environ, {"GOOGLE_CLOUD_PROJECT": "gcp-project"}, clear=True
    ):
        assert _get_project_id() == "gcp-project"


def test_get_project_id_missing():
    with mock.patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError):
            _get_project_id()


def test_fetch_trace_success(mock_trace_service_client):
    # Setup mock
    mock_instance = mock_trace_service_client.return_value
    mock_trace = mock.Mock()
    mock_trace.trace_id = "test_trace_id"
    mock_trace.project_id = "test_project_id"

    mock_span = mock.Mock()
    mock_span.span_id = "span_1"
    mock_span.name = "span_name"
    mock_span.start_time.isoformat.return_value = "2023-01-01T00:00:00Z"
    mock_span.end_time.isoformat.return_value = "2023-01-01T00:00:01Z"
    mock_span.start_time.timestamp.return_value = 1672531200.0
    mock_span.end_time.timestamp.return_value = 1672531201.0
    mock_span.parent_span_id = None
    mock_span.labels = {"key": "value"}

    mock_trace.spans = [mock_span]
    mock_instance.get_trace.return_value = mock_trace

    # Execute
    result_json = fetch_trace("test_project_id", "test_trace_id")
    result = json.loads(result_json)

    # Verify
    mock_instance.get_trace.assert_called_with(
        project_id="test_project_id", trace_id="test_trace_id"
    )
    assert result["trace_id"] == "test_trace_id"
    assert result["project_id"] == "test_project_id"
    assert len(result["spans"]) == 1
    assert result["spans"][0]["span_id"] == "span_1"
    assert result["spans"][0]["labels"]["key"] == "value"


def test_fetch_trace_error(mock_trace_service_client):
    mock_instance = mock_trace_service_client.return_value
    mock_instance.get_trace.side_effect = Exception("API Error")

    from trace_analyzer.tools.trace_cache import get_trace_cache

    get_trace_cache().clear()

    result_json = fetch_trace("test_project_id", "test_trace_id")
    result = json.loads(result_json)

    assert "error" in result
    assert "Failed to fetch trace" in result["error"]


def test_list_traces_success(mock_trace_service_client):
    mock_instance = mock_trace_service_client.return_value

    mock_trace = mock.Mock()
    mock_trace.trace_id = "trace_1"
    mock_trace.project_id = "project_1"
    mock_span = mock.Mock()
    mock_span.start_time.isoformat.return_value = "2023-01-01T00:00:00Z"
    mock_span.end_time = mock.Mock()  # Needed for calculation
    mock_span.start_time = (
        mock.Mock()
    )  # Needed for calculation (datetime object comparison)

    # We need to be careful with the datetime objects for duration calculation
    # Let's mock the span attributes that are accessed
    from datetime import datetime

    s_time = datetime(2023, 1, 1, 0, 0, 0)
    e_time = datetime(2023, 1, 1, 0, 0, 1)

    # Create a wrapper that has isoformat
    mock_span_start = mock.Mock(wraps=s_time)
    mock_span_start.isoformat.return_value = "2023-01-01T00:00:00Z"

    # We need the magic methods for substraction to work
    # But Mock wraps=... usually handles this if we are careful.
    # The issue is that max() and min() will iterate and compare.
    # trace_client.py: starts = [s.start_time for s in trace.spans]
    # Then max(ends) - min(starts)

    # Let's just make sure s.start_time behaves like the datetime object
    # AND has the .isoformat() method mock.

    # Even simpler: attach the method to the real object? No can't do that on builtin.
    # Create a subclass.
    class MockDatetime(datetime):
        def isoformat(self):
            return "2023-01-01T00:00:00Z"

    s_time_mock = MockDatetime(2023, 1, 1, 0, 0, 0)

    mock_span.start_time = s_time_mock
    mock_span.end_time = e_time

    mock_trace.spans = [mock_span]

    mock_instance.list_traces.return_value = [mock_trace]

    result_json = list_traces("project_1")
    result = json.loads(result_json)

    assert len(result) == 1
    assert result[0]["trace_id"] == "trace_1"
    assert result[0]["duration_ms"] == 1000.0


def test_list_traces_error(mock_trace_service_client):
    mock_instance = mock_trace_service_client.return_value
    mock_instance.list_traces.side_effect = Exception("List Error")

    result_json = list_traces("project_1")
    result = json.loads(result_json)

    assert len(result) == 1
    assert "error" in result[0]


def test_find_example_traces_success(mock_env_vars, mock_trace_service_client):
    # Mock list_traces indirectly by mocking the client it uses
    # Or we can patch list_traces. Let's patch list_traces to verify integration logic
    with mock.patch("trace_analyzer.tools.o11y_clients.list_traces") as mock_list:
        mock_list.return_value = json.dumps(
            [
                {"trace_id": "example1", "duration_ms": 100},
                {"trace_id": "example2", "duration_ms": 200},
            ]
        )

        result_json = find_example_traces()
        result = json.loads(result_json)

        mock_list.assert_called()
        assert "stats" in result
        assert "baseline" in result
        assert result["baseline"]["trace_id"] == "example1"


def test_find_example_traces_no_project_id():
    with mock.patch.dict(os.environ, {}, clear=True):
        result_json = find_example_traces()
        result = json.loads(result_json)
        assert "error" in result


def test_get_trace_by_url_success(mock_trace_service_client):
    url = "https://console.cloud.google.com/traces/list?project=test-project&tid=test-trace-id"

    with mock.patch("trace_analyzer.tools.o11y_clients.fetch_trace") as mock_fetch:
        mock_fetch.return_value = json.dumps({"trace_id": "test-trace-id"})

        result_json = get_trace_by_url(url)
        result = json.loads(result_json)

        mock_fetch.assert_called_with("test-project", "test-trace-id")
        assert result["trace_id"] == "test-trace-id"


def test_get_trace_by_url_details_format():
    url = "https://console.cloud.google.com/traces/details/test-trace-id?project=test-project"

    with mock.patch("trace_analyzer.tools.o11y_clients.fetch_trace") as mock_fetch:
        mock_fetch.return_value = json.dumps({"trace_id": "test-trace-id"})

        get_trace_by_url(url)

        mock_fetch.assert_called_with("test-project", "test-trace-id")


def test_get_trace_by_url_invalid():
    url = "https://example.com"
    result_json = get_trace_by_url(url)
    result = json.loads(result_json)
    assert "error" in result
