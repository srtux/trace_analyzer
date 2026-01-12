import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from sre_agent.tools.clients.logging import list_log_entries


def create_mock_page(entries, next_token=None):
    page = MagicMock()
    page.entries = entries
    page.__iter__.return_value = entries
    page.next_page_token = next_token if next_token else ""
    return page


@patch("sre_agent.tools.clients.logging.get_logging_client")
@pytest.mark.asyncio
async def test_list_log_entries_success_text_payload(mock_get_client):
    mock_client = mock_get_client.return_value

    mock_entry = Mock(
        spec=[
            "text_payload",
            "timestamp",
            "severity",
            "resource",
            "json_payload",
            "proto_payload",
            "insert_id",
        ]
    )
    mock_entry.text_payload = "test log content"
    mock_entry.json_payload = None
    mock_entry.proto_payload = None
    mock_entry.timestamp.isoformat.return_value = "2024-01-01T00:00:00Z"
    mock_entry.severity.name = "INFO"
    mock_entry.resource.type = "gce_instance"
    mock_entry.resource.labels = {"instance_id": "123"}
    mock_entry.insert_id = "abc-123"

    mock_pager = MagicMock()
    mock_page = create_mock_page([mock_entry], next_token=None)
    mock_pager.pages = iter([mock_page])
    mock_client.list_log_entries.return_value = mock_pager

    result = await list_log_entries("my-project", "filter")
    data = json.loads(result)

    assert "entries" in data
    assert len(data["entries"]) == 1
    assert data["entries"][0]["payload"] == "test log content"
    assert data["entries"][0]["insert_id"] == "abc-123"
    assert data["next_page_token"] is None

    mock_client.list_log_entries.assert_called_once()
    kwargs = mock_client.list_log_entries.call_args.kwargs
    assert kwargs["request"]["order_by"] == "timestamp desc"
    assert kwargs["request"]["page_size"] == 10


@patch("sre_agent.tools.clients.logging.get_logging_client")
@pytest.mark.asyncio
async def test_list_log_entries_pagination(mock_get_client):
    mock_client = mock_get_client.return_value

    mock_pager = MagicMock()
    mock_page = create_mock_page([], next_token="token-abc")
    mock_pager.pages = iter([mock_page])
    mock_client.list_log_entries.return_value = mock_pager

    result = await list_log_entries("my-project", "filter", limit=5)
    data = json.loads(result)

    assert data["next_page_token"] == "token-abc"

    await list_log_entries("my-project", "filter", limit=5, page_token="token-abc")

    call_args_list = mock_client.list_log_entries.call_args_list
    assert len(call_args_list) == 2
    last_call = call_args_list[1]
    assert last_call.kwargs["request"]["page_token"] == "token-abc"


@patch("sre_agent.tools.clients.logging.get_logging_client")
@pytest.mark.asyncio
async def test_list_log_entries_json_payload(mock_get_client):
    mock_client = mock_get_client.return_value

    mock_entry = Mock(
        spec=[
            "text_payload",
            "timestamp",
            "severity",
            "resource",
            "json_payload",
            "proto_payload",
            "insert_id",
        ]
    )
    mock_entry.text_payload = None
    mock_entry.json_payload = {"key": "value"}
    mock_entry.proto_payload = None
    mock_entry.timestamp.isoformat.return_value = "2024-01-01T00:00:00Z"
    mock_entry.severity.name = "INFO"
    mock_entry.resource.type = "global"
    mock_entry.resource.labels = {}
    mock_entry.insert_id = "1"

    mock_pager = MagicMock()
    mock_page = create_mock_page([mock_entry])
    mock_pager.pages = iter([mock_page])
    mock_client.list_log_entries.return_value = mock_pager

    result = await list_log_entries("p", "f")
    data = json.loads(result)

    assert data["entries"][0]["payload"] == {"key": "value"}


@patch("google.cloud.errorreporting_v1beta1.ErrorStatsServiceClient")
@pytest.mark.asyncio
async def test_list_error_events_success(mock_client_cls):
    mock_client = mock_client_cls.return_value

    mock_event = Mock()
    mock_event.event_time.isoformat.return_value = "2024-01-01T00:00:00Z"
    mock_event.message = "Error occurred"
    mock_event.service_context.service = "web"
    mock_event.service_context.version = "v1"
    mock_client.list_events.return_value = [mock_event]

    from sre_agent.tools.clients.logging import list_error_events

    result = await list_error_events("p")
    data = json.loads(result)

    assert len(data) == 1
    assert data[0]["message"] == "Error occurred"


@patch("google.cloud.errorreporting_v1beta1.ErrorStatsServiceClient")
@pytest.mark.asyncio
async def test_list_error_events_error(mock_client_cls):
    mock_client = mock_client_cls.return_value
    mock_client.list_events.side_effect = Exception("fail")

    from sre_agent.tools.clients.logging import list_error_events

    result = await list_error_events("p")
    data = json.loads(result)
    assert "error" in data
