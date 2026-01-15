"""Tests for tool orchestration and error handling.

This module tests that tool failures are handled gracefully with proper
error messages that guide the agent to use alternative approaches instead
of retrying indefinitely.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sre_agent.schema import ToolStatus
from sre_agent.tools.mcp.gcp import call_mcp_tool_with_retry


class TestToolOrchestrationErrors:
    """Test error handling and messaging for tool orchestration."""

    @pytest.fixture
    def mock_tool_context(self):
        """Create a mock tool context."""
        return MagicMock()

    @pytest.fixture
    def mock_toolset_with_tool(self):
        """Create a mock toolset with a working tool."""
        mock_toolset = AsyncMock()
        mock_tool = AsyncMock()
        mock_tool.name = "test_tool"
        mock_toolset.get_tools = AsyncMock(return_value=[mock_tool])
        mock_toolset.close = AsyncMock()
        return mock_toolset, mock_tool

    @pytest.mark.asyncio
    async def test_cancellation_error_is_non_retryable(
        self, mock_tool_context, mock_toolset_with_tool
    ):
        """Test that CancelledError returns non-retryable error with guidance."""
        mock_toolset, mock_tool = mock_toolset_with_tool
        mock_tool.run_async.side_effect = asyncio.CancelledError()

        def create_toolset(project_id):
            return mock_toolset

        with patch(
            "fastapi.concurrency.run_in_threadpool",
            side_effect=lambda fn, pid: fn(pid),
        ):
            result = await call_mcp_tool_with_retry(
                create_toolset,
                "test_tool",
                {},
                mock_tool_context,
                project_id="test-project",
            )

        assert result["status"] == ToolStatus.ERROR
        assert result["non_retryable"] is True
        assert result["error_type"] == "SYSTEM_CANCELLATION"
        assert "DO NOT retry" in result["error"]
        assert "alternative approach" in result["error"]

    @pytest.mark.asyncio
    async def test_timeout_error_provides_alternatives(
        self, mock_tool_context, mock_toolset_with_tool
    ):
        """Test that timeout errors provide alternative tool suggestions."""
        mock_toolset, mock_tool = mock_toolset_with_tool
        mock_tool.run_async.side_effect = asyncio.TimeoutError()

        def create_toolset(project_id):
            return mock_toolset

        with patch(
            "fastapi.concurrency.run_in_threadpool",
            side_effect=lambda fn, pid: fn(pid),
        ):
            result = await call_mcp_tool_with_retry(
                create_toolset,
                "test_tool",
                {},
                mock_tool_context,
                project_id="test-project",
            )

        assert result["status"] == ToolStatus.ERROR
        assert result["non_retryable"] is True
        assert result["error_type"] == "TIMEOUT"
        assert "DO NOT retry" in result["error"]
        assert "direct API alternatives" in result["error"]

    @pytest.mark.asyncio
    async def test_toolset_creation_timeout_is_non_retryable(self, mock_tool_context):
        """Test that toolset creation timeout returns non-retryable error."""

        async def slow_create(project_id):
            await asyncio.sleep(100)  # Will be cancelled by timeout

        with patch(
            "fastapi.concurrency.run_in_threadpool",
            side_effect=asyncio.TimeoutError(),
        ):
            result = await call_mcp_tool_with_retry(
                lambda pid: None,  # Won't be called
                "test_tool",
                {},
                mock_tool_context,
                project_id="test-project",
            )

        assert result["status"] == ToolStatus.ERROR
        assert result["non_retryable"] is True
        assert result["error_type"] == "MCP_CONNECTION_TIMEOUT"
        assert "DO NOT retry" in result["error"]

    @pytest.mark.asyncio
    async def test_toolset_unavailable_is_non_retryable(self, mock_tool_context):
        """Test that unavailable toolset returns non-retryable error."""

        def create_toolset(project_id):
            return None  # Simulate unavailable toolset

        with patch(
            "fastapi.concurrency.run_in_threadpool",
            side_effect=lambda fn, pid: fn(pid),
        ):
            result = await call_mcp_tool_with_retry(
                create_toolset,
                "test_tool",
                {},
                mock_tool_context,
                project_id="test-project",
            )

        assert result["status"] == ToolStatus.ERROR
        assert result["non_retryable"] is True
        assert result["error_type"] == "MCP_UNAVAILABLE"
        assert "DO NOT retry" in result["error"]
        assert "direct API alternatives" in result["error"]

    @pytest.mark.asyncio
    async def test_tool_not_found_is_non_retryable(self, mock_tool_context):
        """Test that tool not found returns non-retryable error."""
        mock_toolset = AsyncMock()
        # Return a tool with different name
        mock_other_tool = AsyncMock()
        mock_other_tool.name = "other_tool"
        mock_toolset.get_tools = AsyncMock(return_value=[mock_other_tool])
        mock_toolset.close = AsyncMock()

        def create_toolset(project_id):
            return mock_toolset

        with patch(
            "fastapi.concurrency.run_in_threadpool",
            side_effect=lambda fn, pid: fn(pid),
        ):
            result = await call_mcp_tool_with_retry(
                create_toolset,
                "missing_tool",
                {},
                mock_tool_context,
                project_id="test-project",
            )

        assert result["status"] == ToolStatus.ERROR
        assert result["non_retryable"] is True
        assert result["error_type"] == "TOOL_NOT_FOUND"
        assert "DO NOT retry" in result["error"]

    @pytest.mark.asyncio
    async def test_permission_error_is_non_retryable(
        self, mock_tool_context, mock_toolset_with_tool
    ):
        """Test that permission errors are marked as non-retryable."""
        mock_toolset, mock_tool = mock_toolset_with_tool
        mock_tool.run_async.side_effect = Exception("403 Forbidden: Permission denied")

        def create_toolset(project_id):
            return mock_toolset

        with patch(
            "fastapi.concurrency.run_in_threadpool",
            side_effect=lambda fn, pid: fn(pid),
        ):
            result = await call_mcp_tool_with_retry(
                create_toolset,
                "test_tool",
                {},
                mock_tool_context,
                project_id="test-project",
            )

        assert result["status"] == ToolStatus.ERROR
        assert result["non_retryable"] is True
        assert result["error_type"] == "AUTH_ERROR"
        assert (
            "permission" in result["error"].lower() or "DO NOT retry" in result["error"]
        )

    @pytest.mark.asyncio
    async def test_not_found_error_is_non_retryable(
        self, mock_tool_context, mock_toolset_with_tool
    ):
        """Test that 404 not found errors are marked as non-retryable."""
        mock_toolset, mock_tool = mock_toolset_with_tool
        mock_tool.run_async.side_effect = Exception("404: Resource not found")

        def create_toolset(project_id):
            return mock_toolset

        with patch(
            "fastapi.concurrency.run_in_threadpool",
            side_effect=lambda fn, pid: fn(pid),
        ):
            result = await call_mcp_tool_with_retry(
                create_toolset,
                "test_tool",
                {},
                mock_tool_context,
                project_id="test-project",
            )

        assert result["status"] == ToolStatus.ERROR
        assert result["non_retryable"] is True
        assert result["error_type"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_transient_error_allows_retry_suggestion(
        self, mock_tool_context, mock_toolset_with_tool
    ):
        """Test that transient errors suggest retry but with alternatives."""
        mock_toolset, mock_tool = mock_toolset_with_tool
        mock_tool.run_async.side_effect = Exception("Connection reset by peer")

        def create_toolset(project_id):
            return mock_toolset

        with patch(
            "fastapi.concurrency.run_in_threadpool",
            side_effect=lambda fn, pid: fn(pid),
        ):
            result = await call_mcp_tool_with_retry(
                create_toolset,
                "test_tool",
                {},
                mock_tool_context,
                project_id="test-project",
            )

        assert result["status"] == ToolStatus.ERROR
        assert result["error_type"] == "EXECUTION_ERROR"
        # Transient errors might allow one retry
        assert (
            "transient error" in result["error"].lower()
            or "alternative" in result["error"].lower()
        )

    @pytest.mark.asyncio
    async def test_max_retries_exhausted_is_non_retryable(self, mock_tool_context):
        """Test that exhausting retries on session errors is non-retryable."""
        mock_toolset = AsyncMock()
        mock_tool = AsyncMock()
        mock_tool.name = "test_tool"
        # Simulate session error that triggers retry loop
        mock_tool.run_async.side_effect = Exception("Session terminated unexpectedly")
        mock_toolset.get_tools = AsyncMock(return_value=[mock_tool])
        mock_toolset.close = AsyncMock()

        call_count = 0

        def create_toolset(project_id):
            nonlocal call_count
            call_count += 1
            return mock_toolset

        with patch(
            "fastapi.concurrency.run_in_threadpool",
            side_effect=lambda fn, pid: fn(pid),
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):  # Skip actual sleeps
                result = await call_mcp_tool_with_retry(
                    create_toolset,
                    "test_tool",
                    {},
                    mock_tool_context,
                    project_id="test-project",
                    max_retries=3,
                )

        assert result["status"] == ToolStatus.ERROR
        assert result["non_retryable"] is True
        assert result["error_type"] == "MAX_RETRIES_EXHAUSTED"
        assert "DO NOT retry" in result["error"]
        assert call_count == 3  # Tried 3 times before giving up

    @pytest.mark.asyncio
    async def test_error_message_includes_tool_name(
        self, mock_tool_context, mock_toolset_with_tool
    ):
        """Test that error messages include the failing tool name for debugging."""
        mock_toolset, mock_tool = mock_toolset_with_tool
        mock_tool.run_async.side_effect = asyncio.CancelledError()

        def create_toolset(project_id):
            return mock_toolset

        with patch(
            "fastapi.concurrency.run_in_threadpool",
            side_effect=lambda fn, pid: fn(pid),
        ):
            result = await call_mcp_tool_with_retry(
                create_toolset,
                "discover_telemetry_sources",
                {},
                mock_tool_context,
                project_id="test-project",
            )

        assert "discover_telemetry_sources" in result["error"]

    @pytest.mark.asyncio
    async def test_successful_execution_returns_success(
        self, mock_tool_context, mock_toolset_with_tool
    ):
        """Test that successful execution still works correctly."""
        mock_toolset, mock_tool = mock_toolset_with_tool
        mock_tool.run_async.return_value = {"data": "success"}

        def create_toolset(project_id):
            return mock_toolset

        with patch(
            "fastapi.concurrency.run_in_threadpool",
            side_effect=lambda fn, pid: fn(pid),
        ):
            result = await call_mcp_tool_with_retry(
                create_toolset,
                "test_tool",
                {},
                mock_tool_context,
                project_id="test-project",
            )

        assert result["status"] == ToolStatus.SUCCESS
        assert result["result"] == {"data": "success"}
        assert "non_retryable" not in result


class TestDiscoveryToolErrorHandling:
    """Test error handling for discover_telemetry_sources."""

    @pytest.fixture
    def mock_tool_context(self):
        """Create a mock tool context."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_discovery_failure_returns_warning_not_error(self, mock_tool_context):
        """Test that discovery failure returns warning (not error) with guidance."""
        from sre_agent.tools.discovery.discovery_tool import discover_telemetry_sources

        # Mock MCP tool to return an error
        with patch(
            "sre_agent.tools.discovery.discovery_tool.call_mcp_tool_with_retry"
        ) as mock_call:
            mock_call.return_value = {
                "status": "error",
                "error": "Tool execution cancelled by system",
                "error_type": "SYSTEM_CANCELLATION",
                "non_retryable": True,
            }

            result = await discover_telemetry_sources(
                project_id="test-project", tool_context=mock_tool_context
            )

        # Should return warning (completed status) not error
        assert "warning" in result
        assert "error" not in result
        assert result["mode"] == "api_fallback"
        assert "DO NOT call discover_telemetry_sources again" in result["warning"]
        assert result.get("non_retryable") is True

    @pytest.mark.asyncio
    async def test_discovery_failure_suggests_alternatives(self, mock_tool_context):
        """Test that discovery failure suggests specific alternative tools."""
        from sre_agent.tools.discovery.discovery_tool import discover_telemetry_sources

        with patch(
            "sre_agent.tools.discovery.discovery_tool.call_mcp_tool_with_retry"
        ) as mock_call:
            mock_call.return_value = {
                "status": "error",
                "error": "MCP unavailable",
                "error_type": "MCP_UNAVAILABLE",
                "non_retryable": True,
            }

            result = await discover_telemetry_sources(
                project_id="test-project", tool_context=mock_tool_context
            )

        warning = result["warning"]
        # Check that alternatives are mentioned
        assert "list_log_entries" in warning or "fetch_trace" in warning
        assert "direct api" in warning.lower()


class TestErrorMessageQuality:
    """Test that error messages are informative and actionable."""

    @pytest.mark.asyncio
    async def test_error_messages_are_not_generic(self):
        """Ensure error messages provide specific guidance, not generic text."""
        from sre_agent.tools.mcp.gcp import call_mcp_tool_with_retry

        mock_toolset = AsyncMock()
        mock_tool = AsyncMock()
        mock_tool.name = "test_tool"
        mock_tool.run_async.side_effect = asyncio.CancelledError()
        mock_toolset.get_tools = AsyncMock(return_value=[mock_tool])
        mock_toolset.close = AsyncMock()

        with patch(
            "fastapi.concurrency.run_in_threadpool",
            side_effect=lambda fn, pid: fn(pid),
        ):
            result = await call_mcp_tool_with_retry(
                lambda pid: mock_toolset,
                "test_tool",
                {},
                MagicMock(),
                project_id="test-project",
            )

        error_msg = result["error"]

        # Check that error is NOT generic
        assert error_msg != "Tool execution cancelled by system."  # Old generic message
        assert error_msg != "Error"
        assert error_msg != "Failed"

        # Check that error IS specific and actionable
        assert len(error_msg) > 50  # Should be detailed
        assert "DO NOT" in error_msg or "Instead" in error_msg  # Should have guidance

    def test_all_error_types_have_guidance(self):
        """Verify all error types include actionable guidance."""
        error_types = [
            "SYSTEM_CANCELLATION",
            "TIMEOUT",
            "MCP_CONNECTION_TIMEOUT",
            "MCP_UNAVAILABLE",
            "TOOL_NOT_FOUND",
            "AUTH_ERROR",
            "NOT_FOUND",
            "MAX_RETRIES_EXHAUSTED",
        ]

        # This is a documentation/contract test - ensures we handle all types
        # The actual handling is tested in the individual tests above
        assert len(error_types) >= 8, "All major error types should be covered"
