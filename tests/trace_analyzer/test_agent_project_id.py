
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.adk.tools import ToolContext

from trace_analyzer.agent import run_triage_analysis, run_deep_dive_analysis


@pytest.mark.asyncio
async def test_run_triage_analysis_accepts_project_id():
    """Test that run_triage_analysis accepts project_id and passes it to sub-agents."""

    # Mock tool context
    mock_context = MagicMock(spec=ToolContext)

    # Mock AgentTool to capture inputs
    with patch("trace_analyzer.agent.AgentTool") as MockAgentTool:
        mock_tool_instance = AsyncMock()
        mock_tool_instance.run_async.return_value = "Mock Report"
        MockAgentTool.return_value = mock_tool_instance

        # Run triage analysis
        await run_triage_analysis(
            baseline_trace_id="base",
            target_trace_id="target",
            project_id="test-project-id",
            tool_context=mock_context
        )
        
        # Verify it ran the triage agent
        assert MockAgentTool.call_count == 1
        
        # Verify project_id was passed
        call_args = mock_tool_instance.run_async.await_args_list[0]
        request_input = call_args[1]["args"]["request"]
        assert ' "project_id": "test-project-id"' in request_input or "'project_id': 'test-project-id'" in request_input

@pytest.mark.asyncio
async def test_run_deep_dive_analysis_accepts_project_id():
    """Test that run_deep_dive_analysis accepts project_id and passes it to sub-agents."""

    # Mock tool context
    mock_context = MagicMock(spec=ToolContext)

    # Mock AgentTool to capture inputs
    with patch("trace_analyzer.agent.AgentTool") as MockAgentTool:
        mock_tool_instance = AsyncMock()
        mock_tool_instance.run_async.return_value = "Mock Report"
        MockAgentTool.return_value = mock_tool_instance

        # Run deep dive analysis
        await run_deep_dive_analysis(
            baseline_trace_id="base",
            target_trace_id="target",
            stage1_report="Report",
            project_id="test-project-id",
            tool_context=mock_context
        )
        
        # Verify it ran the deep dive agent
        assert MockAgentTool.call_count == 1

        # Verify project_id was passed
        call_args = mock_tool_instance.run_async.await_args_list[0]
        request_input = call_args[1]["args"]["request"]
        assert ' "project_id": "test-project-id"' in request_input or "'project_id': 'test-project-id'" in request_input
