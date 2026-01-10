
import json
from unittest import mock
import pytest
from gcp_observability.tools.clients.monitoring import list_time_series, query_promql

@mock.patch("gcp_observability.tools.clients.monitoring.monitoring_v3.MetricServiceClient")
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


@mock.patch("gcp_observability.tools.clients.monitoring.AuthorizedSession")
@mock.patch("google.auth.default")
def test_query_promql(mock_auth_default, mock_session_cls):
    """Test query_promql tool."""
    mock_auth_default.return_value = (mock.Mock(), "p1")
    mock_session = mock.Mock()
    mock_session_cls.return_value = mock_session

    mock_response = mock.Mock()
    mock_response.json.return_value = {"status": "success", "data": {"result": []}}
    mock_session.get.return_value = mock_response

    result_json = query_promql("p1", "up")
    result = json.loads(result_json)
    
    assert result["status"] == "success"
    mock_session.get.assert_called_once()
    call_args = mock_session.get.call_args
    assert call_args.kwargs["params"]["query"] == "up"
