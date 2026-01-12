from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.adk.tools import ToolContext

from sre_agent.agent import (
    run_aggregate_analysis,
    run_deep_dive_analysis,
    run_log_pattern_analysis,
    run_triage_analysis,
)


@pytest.mark.asyncio
async def test_run_aggregate_analysis_success():
    tool_context = MagicMock(spec=ToolContext)
    with patch("sre_agent.agent.AgentTool") as MockAgentTool:
        mock_instance = MockAgentTool.return_value
        mock_instance.run_async = AsyncMock(return_value="Analysis complete")

        result = await run_aggregate_analysis(
            dataset_id="d", table_name="t", tool_context=tool_context
        )

        assert result["status"] == "success"
        assert result["result"] == "Analysis complete"
        mock_instance.run_async.assert_called_once()


@pytest.mark.asyncio
async def test_run_triage_analysis_success():
    tool_context = MagicMock(spec=ToolContext)
    with patch("sre_agent.agent.get_project_id_with_fallback", return_value="p"):
        with patch("sre_agent.agent.AgentTool") as MockAgentTool:
            mock_instance = MockAgentTool.return_value
            mock_instance.run_async = AsyncMock(return_value="OK")

            result = await run_triage_analysis(
                baseline_trace_id="b", target_trace_id="t", tool_context=tool_context
            )

            assert result["stage"] == "triage"
            results = result["results"]
            assert results["latency"]["status"] == "success"
            assert results["error"]["status"] == "success"
            # 6 agents called in parallel
            assert mock_instance.run_async.await_count == 6


@pytest.mark.asyncio
async def test_run_log_pattern_analysis_success():
    tool_context = MagicMock(spec=ToolContext)
    with patch("sre_agent.agent.get_project_id_with_fallback", return_value="p"):
        with patch("sre_agent.agent.AgentTool") as MockAgentTool:
            mock_instance = MockAgentTool.return_value
            mock_instance.run_async = AsyncMock(return_value="Patterns found")

            result = await run_log_pattern_analysis(
                log_filter="f",
                baseline_start="s1",
                baseline_end="e1",
                comparison_start="s2",
                comparison_end="e2",
                tool_context=tool_context,
            )

            assert result["status"] == "success"
            assert result["result"] == "Patterns found"


@pytest.mark.asyncio
async def test_run_deep_dive_analysis_success():
    tool_context = MagicMock(spec=ToolContext)
    with patch("sre_agent.agent.get_project_id_with_fallback", return_value="p"):
        with patch("sre_agent.agent.AgentTool") as MockAgentTool:
            mock_instance = MockAgentTool.return_value
            mock_instance.run_async = AsyncMock(return_value="Deep dive done")

            result = await run_deep_dive_analysis(
                baseline_trace_id="b",
                target_trace_id="t",
                triage_findings={},
                tool_context=tool_context,
            )

            assert result["stage"] == "deep_dive"
            assert result["results"]["causality"]["status"] == "success"
            # 3 agents called
            assert mock_instance.run_async.await_count == 3
