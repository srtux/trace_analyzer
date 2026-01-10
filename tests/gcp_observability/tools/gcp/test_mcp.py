
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, ANY
from gcp_observability.tools.gcp.mcp import (
    create_bigquery_mcp_toolset,
    create_logging_mcp_toolset,
    create_monitoring_mcp_toolset,
    mcp_list_log_entries,
    mcp_list_timeseries,
    mcp_query_range,
)
from google.adk.tools import ToolContext

# =============================================================================
# Logging
# =============================================================================

@pytest.mark.asyncio
async def test_mcp_list_log_entries_no_context():
    with pytest.raises(ValueError, match="tool_context is required"):
        await mcp_list_log_entries(filter="f", tool_context=None)

@pytest.mark.asyncio
async def test_mcp_list_log_entries_success():
    tool_context = MagicMock(spec=ToolContext)
    mock_toolset = AsyncMock()
    mock_tool = AsyncMock()
    mock_tool.name = "list_log_entries"
    mock_tool.run_async.return_value = {"entries": []}
    mock_toolset.get_tools.return_value = [mock_tool]

    with patch("gcp_observability.tools.gcp.mcp.get_project_id_with_fallback", return_value="test-project"):
        with patch("gcp_observability.tools.gcp.mcp.create_logging_mcp_toolset", return_value=mock_toolset):
            result = await mcp_list_log_entries(
                filter="severity=ERROR",
                tool_context=tool_context
            )
            assert result["source"] == "mcp"
            assert result["result"] == {"entries": []}
            mock_tool.run_async.assert_called_once()
            call_args = mock_tool.run_async.call_args[1]["args"]
            assert call_args["filter"] == "severity=ERROR"
            assert call_args["resource_names"] == ["projects/test-project"]

@pytest.mark.asyncio
async def test_mcp_list_log_entries_toolset_fail():
    tool_context = MagicMock(spec=ToolContext)
    with patch("gcp_observability.tools.gcp.mcp.get_project_id_with_fallback", return_value="test-project"):
        with patch("gcp_observability.tools.gcp.mcp.create_logging_mcp_toolset", return_value=None):
            result = await mcp_list_log_entries(filter="foo", tool_context=tool_context)
            assert "error" in result
            assert "unavailable" in result["error"]

def test_create_logging_mcp_toolset_no_project():
    with patch("gcp_observability.tools.gcp.mcp.get_project_id_with_fallback", return_value=None):
        assert create_logging_mcp_toolset() is None

def test_create_logging_mcp_toolset_success():
    with patch("gcp_observability.tools.gcp.mcp.get_project_id_with_fallback", return_value="p"):
        with patch("gcp_observability.tools.gcp.mcp.ApiRegistry") as MockRegistry:
            toolset = create_logging_mcp_toolset("p")
            assert toolset is not None
            MockRegistry.assert_called_with("p", header_provider=ANY)

# =============================================================================
# Monitoring
# =============================================================================

@pytest.mark.asyncio
async def test_mcp_list_timeseries_success():
    tool_context = MagicMock(spec=ToolContext)
    mock_toolset = AsyncMock()
    mock_tool = AsyncMock()
    mock_tool.name = "list_timeseries"
    mock_tool.run_async.return_value = {"timeSeries": []}
    mock_toolset.get_tools.return_value = [mock_tool]

    with patch("gcp_observability.tools.gcp.mcp.get_project_id_with_fallback", return_value="test-project"):
        with patch("gcp_observability.tools.gcp.mcp.create_monitoring_mcp_toolset", return_value=mock_toolset):
            result = await mcp_list_timeseries(
                filter="metric.type=\"compute\"",
                minutes_ago=10,
                tool_context=tool_context
            )
            assert result["source"] == "mcp"
            assert result["result"] == {"timeSeries": []}

@pytest.mark.asyncio
async def test_mcp_query_range_success():
    tool_context = MagicMock(spec=ToolContext)
    mock_toolset = AsyncMock()
    mock_tool = AsyncMock()
    mock_tool.name = "query_range"
    mock_tool.run_async.return_value = {"results": []}
    mock_toolset.get_tools.return_value = [mock_tool]

    with patch("gcp_observability.tools.gcp.mcp.get_project_id_with_fallback", return_value="test-project"):
        with patch("gcp_observability.tools.gcp.mcp.create_monitoring_mcp_toolset", return_value=mock_toolset):
            result = await mcp_query_range(
                query="fetch",
                tool_context=tool_context
            )
            assert result["source"] == "mcp"

def test_create_monitoring_mcp_toolset_success():
    with patch("gcp_observability.tools.gcp.mcp.ApiRegistry") as MockRegistry:
        toolset = create_monitoring_mcp_toolset("p")
        assert toolset is not None

# =============================================================================
# BigQuery
# =============================================================================

def test_create_bigquery_mcp_toolset_success():
    with patch("gcp_observability.tools.gcp.mcp.ApiRegistry") as MockRegistry:
        toolset = create_bigquery_mcp_toolset("p")
        assert toolset is not None
        MockRegistry.assert_called_with("p", header_provider=ANY)

def test_create_bigquery_mcp_toolset_fail():
    with patch("gcp_observability.tools.gcp.mcp.get_project_id_with_fallback", return_value=None):
        assert create_bigquery_mcp_toolset() is None
