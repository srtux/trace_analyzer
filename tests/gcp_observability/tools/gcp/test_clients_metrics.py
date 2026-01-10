
import pytest
import json
import uuid
import sys
from unittest.mock import patch, MagicMock
from gcp_observability.tools.gcp.clients import list_time_series, list_error_events

@patch("gcp_observability.tools.gcp.clients.monitoring_v3")
def test_list_time_series_success(mock_monitoring):
    mock_client = mock_monitoring.MetricServiceClient.return_value
    
    # Mock result structure
    mock_point = MagicMock()
    mock_point.interval.end_time.isoformat.return_value = "2024-01-01T00:00:00Z"
    mock_point.value.double_value = 100.0
    
    mock_ts = MagicMock()
    mock_ts.metric.type = "cpu"
    mock_ts.metric.labels = {"instance": "i-1"}
    mock_ts.resource.type = "gce_instance"
    mock_ts.resource.labels = {"zone": "us-central1-a"}
    mock_ts.points = [mock_point]
    
    mock_client.list_time_series.return_value = [mock_ts]
    
    result = list_time_series("p", "filter")
    data = json.loads(result)
    
    assert len(data) == 1
    assert data[0]["metric"]["type"] == "cpu"

@patch("gcp_observability.tools.gcp.clients.monitoring_v3")
def test_list_time_series_error(mock_monitoring):
    mock_client = mock_monitoring.MetricServiceClient.return_value
    mock_client.list_time_series.side_effect = Exception("API error")
    
    result = list_time_series("p", "filter")
    data = json.loads(result)
    assert "error" in data

def test_list_error_events_success():
    # Use patch directly on the class path that will be imported
    with patch("google.cloud.errorreporting_v1beta1.ErrorStatsServiceClient") as MockClient:
        mock_client = MockClient.return_value
        mock_event = MagicMock()
        mock_event.event_time.isoformat.return_value = "2024-01-01T00:00:00Z"
        mock_event.message = "Error occurred"
        mock_event.service_context.service = "web"
        mock_event.service_context.version = "v1"
        mock_client.list_events.return_value = [mock_event]
        
        result = list_error_events("p")
        data = json.loads(result)
        
        assert len(data) == 1
        assert data[0]["message"] == "Error occurred"

def test_list_error_events_error():
    with patch("google.cloud.errorreporting_v1beta1.ErrorStatsServiceClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.list_events.side_effect = Exception("fail")
        
        result = list_error_events("p")
        data = json.loads(result)
        assert "error" in data
