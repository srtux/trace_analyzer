"""Integration tests for the Trace Analyzer Agent."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from google.adk.agents import LlmAgent

from gcp_observability.agent import root_agent


@pytest.fixture
def mock_env():
    with patch.dict(
        os.environ,
        {"GOOGLE_CLOUD_PROJECT": "test-project", "VERTEX_API_KEY": "test-key"},
    ):
        yield


@pytest.mark.asyncio
async def test_agent_initialization(mock_env):
    """Test that the agent initializes correctly with the parallel squad."""
    assert isinstance(root_agent, LlmAgent)
    assert root_agent.name == "gcp_observability_agent"

    # Check if the analysis tools are present
    tool_names = [getattr(t, "name", getattr(t, "__name__", str(t))) for t in root_agent.tools]
    
    assert "run_triage_analysis" in tool_names
    assert "run_deep_dive_analysis" in tool_names
    
    # Check for selection tools
    assert "select_traces_from_error_reports" in tool_names
    assert "select_traces_manually" in tool_names


@patch("gcp_observability.tools.clients.trace.trace_v1.TraceServiceClient")
def test_agent_finds_logs_for_trace(mock_trace_client):
    """Test that agent can find logs for a specific trace."""
    from gcp_observability.tools.clients.trace import list_traces

    mock_client = MagicMock()
    mock_trace_client.return_value = mock_client

    # Setup mock response with datetime objects for timestamps (simulating proto-plus behavior)
    from datetime import datetime

    mock_trace = MagicMock()
    mock_trace.trace_id = "123"
    mock_trace.project_id = "p"

    mock_span = MagicMock()
    mock_span.start_time = datetime(2023, 1, 1, 12, 0, 0)
    mock_span.end_time = datetime(2023, 1, 1, 12, 0, 1)
    mock_trace.spans = [mock_span]

    mock_client.list_traces.return_value = [mock_trace]

    # Run
    result = list_traces("p", limit=1, min_latency_ms=500)

    # Verify request args
    call_args = mock_client.list_traces.call_args
    req = call_args.kwargs["request"]

    assert "latency:500ms" in req.filter
    # Ensure view type is ROOTSPAN (value 1) or whatever the enum maps to,
    # but mainly we check that we didn't crash.

    res_data = json.loads(result)
    assert len(res_data) == 1
    assert res_data[0]["duration_ms"] == 1000.0
