
import json
from unittest import mock

from trace_analyzer.tools.trace_client import (
    list_error_events,
    list_log_entries,
    list_time_series,
)


@mock.patch("trace_analyzer.tools.trace_client.LoggingServiceV2Client")
def test_list_log_entries(mock_logging_client_cls):
    """Test list_log_entries tool."""
    mock_client = mock.Mock()
    mock_logging_client_cls.return_value = mock_client

    # Mock LogEntry
    mock_entry = mock.Mock()
    mock_entry.payload = "log_payload"
    mock_entry.timestamp.isoformat.return_value = "2023-01-01T00:00:00Z"
    mock_entry.severity.name = "INFO"
    mock_entry.resource.type = "global"
    mock_entry.resource.labels = {"key": "value"}

    mock_client.list_log_entries.return_value = [mock_entry]

    result_json = list_log_entries("p1", "filter", 1)
    result = json.loads(result_json)

    assert len(result) == 1
    assert result[0]["payload"] == "log_payload"
    mock_client.list_log_entries.assert_called_with(
        request={
            "resource_names": ["projects/p1"],
            "filter": "filter",
            "page_size": 1
        }
    )

@mock.patch("trace_analyzer.tools.trace_client.monitoring_v3.MetricServiceClient")
def test_list_time_series(mock_metric_client_cls):
    """Test list_time_series tool."""
    mock_client = mock.Mock()
    mock_metric_client_cls.return_value = mock_client

    # Mock TimeSeries
    mock_ts = mock.Mock()
    mock_ts.metric.type = "metric_type"
    mock_ts.metric.labels = {"l1": "v1"}
    mock_ts.resource.type = "res_type"
    mock_ts.resource.labels = {"l2": "v2"}

    mock_point = mock.Mock()
    mock_point.interval.end_time.isoformat.return_value = "2023-01-01T00:00:00Z"
    mock_point.value.double_value = 100.0
    mock_ts.points = [mock_point]

    mock_client.list_time_series.return_value = [mock_ts]

    result_json = list_time_series("p1", "filter", 60)
    result = json.loads(result_json)

    assert len(result) == 1
    assert result[0]["metric"]["type"] == "metric_type"
    assert result[0]["points"][0]["value"] == 100.0

@mock.patch("trace_analyzer.tools.trace_client.errorreporting_v1beta1.ErrorStatsServiceClient")
def test_list_error_events(mock_error_client_cls):
    """Test list_error_events tool."""
    mock_client = mock.Mock()
    mock_error_client_cls.return_value = mock_client

    mock_event = mock.Mock()
    mock_event.event_time.isoformat.return_value = "2023-01-01T00:00:00Z"
    mock_event.message = "error message"
    mock_event.service_context.service = "service"
    mock_event.service_context.version = "v1"

    mock_client.list_events.return_value = [mock_event]

    result_json = list_error_events("p1", 60)
    result = json.loads(result_json)

    assert len(result) == 1
    assert result[0]["message"] == "error message"
