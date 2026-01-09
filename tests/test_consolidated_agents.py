"""Tests for the consolidated agent architecture.

Tests verify that:
1. trace_investigator agent is properly configured with correct tools
2. root_cause_analyzer agent is properly configured with correct tools
3. Agent orchestration functions work correctly
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.adk.agents import Agent


class TestTraceInvestigatorAgent:
    """Tests for the consolidated trace_investigator agent."""

    def test_agent_exists_and_configured(self):
        """Test that trace_investigator is properly configured."""
        from trace_analyzer.sub_agents.investigator.agent import trace_investigator

        assert isinstance(trace_investigator, Agent)
        assert trace_investigator.name == "trace_investigator"
        assert "gemini" in trace_investigator.model.lower()

    def test_agent_has_required_tools(self):
        """Test that trace_investigator has all required analysis tools."""
        from trace_analyzer.sub_agents.investigator.agent import trace_investigator

        tool_names = [
            getattr(t, "name", getattr(t, "__name__", str(t)))
            for t in trace_investigator.tools
        ]

        # Core tools that should be present
        required_tools = [
            "fetch_trace",
            "compare_span_timings",
            "extract_errors",
            "build_call_graph",
            "find_structural_differences",
        ]

        for tool in required_tools:
            assert tool in tool_names, f"Missing required tool: {tool}"

    def test_agent_has_statistical_tools(self):
        """Test that trace_investigator has statistical analysis tools."""
        from trace_analyzer.sub_agents.investigator.agent import trace_investigator

        tool_names = [
            getattr(t, "name", getattr(t, "__name__", str(t)))
            for t in trace_investigator.tools
        ]

        statistical_tools = [
            "compute_latency_statistics",
            "detect_latency_anomalies",
            "analyze_critical_path",
        ]

        for tool in statistical_tools:
            assert tool in tool_names, f"Missing statistical tool: {tool}"

    def test_agent_instruction_contains_key_sections(self):
        """Test that agent instruction has necessary guidance."""
        from trace_analyzer.sub_agents.investigator.agent import trace_investigator

        instruction = trace_investigator.instruction.lower()

        # Should contain analysis capability descriptions
        assert "latency" in instruction
        assert "error" in instruction
        assert "structure" in instruction

        # Should mention output format
        assert "json" in instruction


class TestRootCauseAnalyzerAgent:
    """Tests for the consolidated root_cause_analyzer agent."""

    def test_agent_exists_and_configured(self):
        """Test that root_cause_analyzer is properly configured."""
        from trace_analyzer.sub_agents.root_cause.agent import root_cause_analyzer

        assert isinstance(root_cause_analyzer, Agent)
        assert root_cause_analyzer.name == "root_cause_analyzer"
        assert "gemini" in root_cause_analyzer.model.lower()

    def test_agent_has_required_tools(self):
        """Test that root_cause_analyzer has all required analysis tools."""
        from trace_analyzer.sub_agents.root_cause.agent import root_cause_analyzer

        tool_names = [
            getattr(t, "name", getattr(t, "__name__", str(t)))
            for t in root_cause_analyzer.tools
        ]

        # Core tools that should be present
        required_tools = [
            "fetch_trace",
            "perform_causal_analysis",
            "analyze_critical_path",
            "compute_service_level_stats",
        ]

        for tool in required_tools:
            assert tool in tool_names, f"Missing required tool: {tool}"

    def test_agent_instruction_contains_key_sections(self):
        """Test that agent instruction has necessary guidance."""
        from trace_analyzer.sub_agents.root_cause.agent import root_cause_analyzer

        instruction = root_cause_analyzer.instruction.lower()

        # Should contain root cause methodology
        assert "causal" in instruction or "root cause" in instruction
        assert "impact" in instruction

        # Should mention output format
        assert "json" in instruction


class TestAgentOrchestration:
    """Tests for the agent orchestration functions."""

    @pytest.mark.asyncio
    async def test_run_investigation_calls_agent(self):
        """Test that run_investigation properly invokes the trace_investigator."""
        from trace_analyzer.agent import run_investigation
        from google.adk.tools import ToolContext

        mock_context = MagicMock(spec=ToolContext)

        with patch("trace_analyzer.agent.AgentTool") as MockAgentTool:
            mock_tool_instance = AsyncMock()
            mock_tool_instance.run_async.return_value = {"result": "investigation_report"}
            MockAgentTool.return_value = mock_tool_instance

            result = await run_investigation(
                baseline_trace_id="baseline-123",
                target_trace_id="target-456",
                project_id="test-project",
                tool_context=mock_context,
            )

            # Verify AgentTool was created with trace_investigator
            assert MockAgentTool.call_count == 1

            # Verify run_async was called
            mock_tool_instance.run_async.assert_called_once()

            # Verify the request contains the trace IDs
            call_args = mock_tool_instance.run_async.call_args
            request = call_args[1]["args"]["request"]
            assert "baseline-123" in request
            assert "target-456" in request

    @pytest.mark.asyncio
    async def test_run_root_cause_analysis_calls_agent(self):
        """Test that run_root_cause_analysis properly invokes the root_cause_analyzer."""
        from trace_analyzer.agent import run_root_cause_analysis
        from google.adk.tools import ToolContext

        mock_context = MagicMock(spec=ToolContext)

        with patch("trace_analyzer.agent.AgentTool") as MockAgentTool:
            mock_tool_instance = AsyncMock()
            mock_tool_instance.run_async.return_value = {"result": "root_cause_report"}
            MockAgentTool.return_value = mock_tool_instance

            result = await run_root_cause_analysis(
                baseline_trace_id="baseline-123",
                target_trace_id="target-456",
                investigation_report="Previous investigation findings...",
                project_id="test-project",
                tool_context=mock_context,
            )

            # Verify AgentTool was created with root_cause_analyzer
            assert MockAgentTool.call_count == 1

            # Verify run_async was called
            mock_tool_instance.run_async.assert_called_once()

            # Verify the request contains the investigation report
            call_args = mock_tool_instance.run_async.call_args
            request = call_args[1]["args"]["request"]
            assert "Previous investigation findings" in request

    @pytest.mark.asyncio
    async def test_run_aggregate_analysis_calls_agent(self):
        """Test that run_aggregate_analysis properly invokes the aggregate_analyzer."""
        from trace_analyzer.agent import run_aggregate_analysis
        from google.adk.tools import ToolContext

        mock_context = MagicMock(spec=ToolContext)

        with patch("trace_analyzer.agent.AgentTool") as MockAgentTool:
            mock_tool_instance = AsyncMock()
            mock_tool_instance.run_async.return_value = {"result": "aggregate_report"}
            MockAgentTool.return_value = mock_tool_instance

            result = await run_aggregate_analysis(
                dataset_id="project.telemetry",
                time_window_hours=24,
                service_name="user-service",
                tool_context=mock_context,
            )

            # Verify AgentTool was called
            assert MockAgentTool.call_count == 1

            # Verify run_async was called
            mock_tool_instance.run_async.assert_called_once()

            # Verify the request contains dataset info
            call_args = mock_tool_instance.run_async.call_args
            request = call_args[1]["args"]["request"]
            assert "project.telemetry" in request
            assert "24" in request

    @pytest.mark.asyncio
    async def test_orchestration_requires_tool_context(self):
        """Test that orchestration functions require tool_context."""
        from trace_analyzer.agent import run_investigation, run_root_cause_analysis

        with pytest.raises(ValueError, match="tool_context is required"):
            await run_investigation(
                baseline_trace_id="base",
                target_trace_id="target",
                tool_context=None,
            )

        with pytest.raises(ValueError, match="tool_context is required"):
            await run_root_cause_analysis(
                baseline_trace_id="base",
                target_trace_id="target",
                investigation_report="report",
                tool_context=None,
            )


class TestRootAgentConfiguration:
    """Tests for the root agent configuration."""

    def test_root_agent_has_orchestration_tools(self):
        """Test that root agent has the orchestration tools."""
        from trace_analyzer.agent import root_agent

        tool_names = [
            getattr(t, "name", getattr(t, "__name__", str(t)))
            for t in root_agent.tools
        ]

        orchestration_tools = [
            "run_aggregate_analysis",
            "run_investigation",
            "run_root_cause_analysis",
        ]

        for tool in orchestration_tools:
            assert tool in tool_names, f"Missing orchestration tool: {tool}"

    def test_root_agent_has_sre_pattern_tools(self):
        """Test that root agent has SRE pattern detection tools."""
        from trace_analyzer.agent import root_agent

        tool_names = [
            getattr(t, "name", getattr(t, "__name__", str(t)))
            for t in root_agent.tools
        ]

        sre_tools = [
            "detect_all_sre_patterns",
            "detect_retry_storm",
            "detect_cascading_timeout",
            "detect_connection_pool_issues",
        ]

        for tool in sre_tools:
            assert tool in tool_names, f"Missing SRE pattern tool: {tool}"

    def test_root_agent_has_direct_trace_tools(self):
        """Test that root agent has direct trace access tools."""
        from trace_analyzer.agent import root_agent

        tool_names = [
            getattr(t, "name", getattr(t, "__name__", str(t)))
            for t in root_agent.tools
        ]

        direct_tools = [
            "fetch_trace",
            "list_traces",
            "summarize_trace",
        ]

        for tool in direct_tools:
            assert tool in tool_names, f"Missing direct tool: {tool}"

    def test_root_agent_tool_count_reduced(self):
        """Test that root agent has a reasonable number of tools (simplified)."""
        from trace_analyzer.agent import root_agent

        # With the simplified architecture, we should have fewer tools
        # (3 orchestration + ~10 direct + 4 SRE + 5 BigQuery + optional MCP)
        tool_count = len(root_agent.tools)

        # Should be between 15-25 tools (not 30+ like before)
        assert tool_count < 30, f"Too many tools: {tool_count}"
        assert tool_count >= 15, f"Too few tools: {tool_count}"
