"""Tests for discover_telemetry_sources tool."""

from unittest.mock import AsyncMock, patch

import pytest

from sre_agent.tools.discovery.discovery_tool import discover_telemetry_sources


@pytest.mark.asyncio
async def test_dlp_discovery_success(mock_tool_context):
    """Test successful discovery of both traces and logs tables."""

    # Mock create_bigquery_mcp_toolset to return a mock toolset
    mock_toolset = AsyncMock()

    # Mock tools within toolset
    mock_list_datasets = AsyncMock()
    mock_list_datasets.name = "list_dataset_ids"
    mock_list_datasets.run_async.return_value = ["my_dataset"]

    mock_list_tables = AsyncMock()
    mock_list_tables.name = "list_table_ids"
    mock_list_tables.run_async.return_value = ["_AllSpans", "_AllLogs"]

    mock_toolset.get_tools.return_value = [mock_list_datasets, mock_list_tables]

    with patch(
        "sre_agent.tools.discovery.discovery_tool.create_bigquery_mcp_toolset",
        return_value=mock_toolset,
    ):
        result = await discover_telemetry_sources(
            project_id="test-project", tool_context=mock_tool_context
        )

        assert result["mode"] == "bigquery"
        assert result["trace_table"] == "test-project.my_dataset._AllSpans"
        assert result["log_table"] == "test-project.my_dataset._AllLogs"


@pytest.mark.asyncio
async def test_dlp_discovery_partial(mock_tool_context):
    """Test discovery where only traces are found."""

    mock_toolset = AsyncMock()

    mock_list_datasets = AsyncMock()
    mock_list_datasets.name = "list_dataset_ids"
    mock_list_datasets.run_async.return_value = ["dataset1", "dataset2"]

    mock_list_tables = AsyncMock()
    mock_list_tables.name = "list_table_ids"
    # dataset1 has nothing, dataset2 has spans
    mock_list_tables.run_async.side_effect = [[], ["_AllSpans"]]

    mock_toolset.get_tools.return_value = [mock_list_datasets, mock_list_tables]

    with patch(
        "sre_agent.tools.discovery.discovery_tool.create_bigquery_mcp_toolset",
        return_value=mock_toolset,
    ):
        result = await discover_telemetry_sources(
            project_id="test-project", tool_context=mock_tool_context
        )

        assert result["mode"] == "bigquery"
        assert result["trace_table"] == "test-project.dataset2._AllSpans"
        assert result["log_table"] is None


@pytest.mark.asyncio
async def test_dlp_discovery_fallback(mock_tool_context):
    """Test fallback when no tables are found."""

    mock_toolset = AsyncMock()

    mock_list_datasets = AsyncMock()
    mock_list_datasets.name = "list_dataset_ids"
    mock_list_datasets.run_async.return_value = ["dataset1"]

    mock_list_tables = AsyncMock()
    mock_list_tables.name = "list_table_ids"
    mock_list_tables.run_async.return_value = ["some_other_table"]

    mock_toolset.get_tools.return_value = [mock_list_datasets, mock_list_tables]

    with patch(
        "sre_agent.tools.discovery.discovery_tool.create_bigquery_mcp_toolset",
        return_value=mock_toolset,
    ):
        result = await discover_telemetry_sources(
            project_id="test-project", tool_context=mock_tool_context
        )

        assert result["mode"] == "api_fallback"
        assert result["trace_table"] is None
