import json
from unittest.mock import patch

import pytest

from sre_agent.tools.clients.trace import find_example_traces, get_trace_by_url


@pytest.mark.asyncio
@patch("sre_agent.tools.clients.trace.list_traces")
@patch("sre_agent.tools.clients.trace._get_project_id", return_value="p")
async def test_find_example_traces_hybrid(mock_pid, mock_list_traces):
    # Setup mock traces
    # 50 normal traces (around 100ms)
    traces = [
        {"trace_id": f"t{i}", "duration_ms": 100 + i, "project_id": "p"}
        for i in range(50)
    ]
    # Add one valid anomaly (500ms)
    traces.append({"trace_id": "t_slow", "duration_ms": 500, "project_id": "p"})

    mock_list_traces.return_value = json.dumps(traces)

    # Call function
    result_json = await find_example_traces(project_id="p", prefer_errors=False)
    result = json.loads(result_json)

    assert "baseline" in result
    assert "anomaly" in result
    assert "stats" in result

    # Baseline should be close to median (100-150 range)
    assert 100 <= result["baseline"]["duration_ms"] <= 150
    # Anomaly should be the slow one
    assert result["anomaly"]["trace_id"] == "t_slow"
    assert result["stats"]["count"] == 51


@pytest.mark.asyncio
@patch("sre_agent.tools.clients.trace.fetch_trace")
async def test_get_trace_by_url_success(mock_fetch_trace):
    url = "https://console.cloud.google.com/traces/list?project=my-project&tid=1234567890abcdef"
    mock_fetch_trace.return_value = json.dumps({"trace_id": "1234567890abcdef"})

    result = await get_trace_by_url(url)
    data = json.loads(result)

    assert data["trace_id"] == "1234567890abcdef"
    mock_fetch_trace.assert_called_with("my-project", "1234567890abcdef")


@pytest.mark.asyncio
@patch("sre_agent.tools.clients.trace.fetch_trace")
async def test_get_trace_by_url_details_path(mock_fetch_trace):
    url = "https://console.cloud.google.com/traces/list/details/1234567890abcdef?project=my-project"
    mock_fetch_trace.return_value = json.dumps({"trace_id": "1234567890abcdef"})

    result = await get_trace_by_url(url)
    data = json.loads(result)

    assert data["trace_id"] == "1234567890abcdef"


@pytest.mark.asyncio
async def test_get_trace_by_url_invalid():
    url = "https://google.com"
    result = await get_trace_by_url(url)
    data = json.loads(result)
    assert "error" in data
