from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.adk.tools import ToolContext

from sre_agent.agent import run_deep_dive_analysis, run_triage_analysis


@pytest.mark.asyncio
async def test_run_triage_analysis_accepts_project_id():
    """Test that run_triage_analysis accepts project_id and passes it to sub-agents."""

    # Mock tool context
    mock_context = MagicMock(spec=ToolContext)

    # Mock AgentTool to capture inputs
    with patch("sre_agent.agent.AgentTool") as MockAgentTool:
        mock_tool_instance = AsyncMock()
        MockAgentTool.return_value = mock_tool_instance
        mock_tool_instance.run_async.return_value = "Mock Report"

        # Run triage analysis
        await run_triage_analysis(
            baseline_trace_id="base",
            target_trace_id="target",
            project_id="test-project-id",
            tool_context=mock_context,
        )

        # Verify it ran the triage agents (6 of them)
        assert MockAgentTool.call_count == 6
        assert mock_tool_instance.run_async.call_count == 6

        # Verify project_id was passed in request
        call_args = mock_tool_instance.run_async.call_args_list[0]
        request = call_args.kwargs.get("args", {}).get("request")

        assert request is not None
        assert "test-project-id" in request


@pytest.mark.asyncio
async def test_run_deep_dive_analysis_accepts_project_id():
    """Test that run_deep_dive_analysis accepts project_id and passes it to sub-agents."""

    # Mock tool context
    mock_context = MagicMock(spec=ToolContext)

    # Mock AgentTool to capture inputs
    with patch("sre_agent.agent.AgentTool") as MockAgentTool:
        mock_tool_instance = AsyncMock()
        MockAgentTool.return_value = mock_tool_instance
        mock_tool_instance.run_async.return_value = "Mock Report"

        # Run deep dive analysis
        await run_deep_dive_analysis(
            baseline_trace_id="base",
            target_trace_id="target",
            triage_findings={"results": {}},
            project_id="test-project-id",
            tool_context=mock_context,
        )

        # Verify it ran the deep dive agents (3 of them)
        assert MockAgentTool.call_count == 3
        assert mock_tool_instance.run_async.call_count == 3

        # Verify project_id was passed in request
        call_args = mock_tool_instance.run_async.call_args_list[0]
        request = call_args.kwargs.get("args", {}).get("request")

        assert request is not None
        assert "test-project-id" in request
