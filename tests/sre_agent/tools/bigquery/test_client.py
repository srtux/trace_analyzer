"""Tests for BigQuery Client."""

from unittest.mock import AsyncMock, patch

import pytest

from sre_agent.tools.bigquery.client import BigQueryClient


@pytest.mark.asyncio
async def test_execute_query_success(mock_tool_context):
    """Test successful query execution."""
    mock_toolset = AsyncMock()
    mock_execute = AsyncMock()
    mock_execute.name = "execute_sql"
    mock_execute.run_async.return_value = {"rows": [{"col": "val"}]}
    mock_toolset.get_tools.return_value = [mock_execute]

    client = BigQueryClient(project_id="test-project", tool_context=mock_tool_context)

    with patch(
        "sre_agent.tools.bigquery.client.create_bigquery_mcp_toolset",
        return_value=mock_toolset,
    ):
        rows = await client.execute_query("SELECT 1")
        assert len(rows) == 1
        assert rows[0]["col"] == "val"


@pytest.mark.asyncio
async def test_get_table_schema_success(mock_tool_context):
    """Test getting table schema."""
    mock_toolset = AsyncMock()
    mock_get_info = AsyncMock()
    mock_get_info.name = "get_table_info"
    mock_get_info.run_async.return_value = {
        "schema": {"fields": [{"name": "col1", "type": "STRING"}]}
    }
    mock_toolset.get_tools.return_value = [mock_get_info]

    client = BigQueryClient(project_id="test-project", tool_context=mock_tool_context)

    with patch(
        "sre_agent.tools.bigquery.client.create_bigquery_mcp_toolset",
        return_value=mock_toolset,
    ):
        fields = await client.get_table_schema("ds", "tbl")
        assert len(fields) == 1
        assert fields[0]["name"] == "col1"
