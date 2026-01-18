import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# We need to import the app from server.py
# Since server.py is in the root, we might need to add it to path or import nicely.
# Assuming we can import it if we are running from root.
from server import app

client = TestClient(app)


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="TestClient streaming with async generators has synchronization issues. "
    "The mock agent's run_async is called but events aren't yielded before the "
    "response completes. This test needs refactoring to use an async test client."
)
async def test_genui_chat_tool_log_events():
    """Verify that tool calls emit x-sre-tool-log events."""

    # Mock the root_agent to yield specific events
    # We need to mock root_agent.run_async

    mock_agent = MagicMock()

    # Create mock parts for the function call and response cycle

    # 1. Function Call Event
    mock_part_call = MagicMock()
    mock_part_call.text = None
    mock_part_call.function_call.name = "test_tool"
    mock_part_call.function_call.args = {"arg1": "value1"}
    mock_part_call.function_response = None

    mock_event_call = MagicMock()
    mock_event_call.content.parts = [mock_part_call]

    # 2. Function Response Event
    mock_part_response = MagicMock()
    mock_part_response.text = None
    mock_part_response.function_call = None
    mock_part_response.function_response.name = "test_tool"
    mock_part_response.function_response.response = {"result": "success"}

    mock_event_response = MagicMock()
    mock_event_response.content.parts = [mock_part_response]

    # Setup the async generator mock
    async def mock_run_async(*args, **kwargs):
        yield mock_event_call
        yield mock_event_response

    mock_agent.run_async = mock_run_async
    mock_agent.clone.return_value = mock_agent  # Handle cloning

    # Patch the root_agent and session manager in server.py
    with patch("server.root_agent", mock_agent):
        # Mock session manager to return a mock session
        mock_session = MagicMock()
        mock_session.id = "test-session"
        mock_session.events = []

        mock_session_manager = MagicMock()
        mock_session_manager.get_or_create_session = AsyncMock(
            return_value=mock_session
        )
        mock_session_manager.session_service.append_event = AsyncMock()

        with patch("server.get_session_service", return_value=mock_session_manager):
            # Send request
            response = client.post(
                "/api/genui/chat",
                json={"messages": [{"role": "user", "text": "Run test tool"}]},
            )
            assert response.status_code == 200

        # Parse NDJSON stream
        lines = response.text.strip().split("\n")

        tool_logs = []

        for line in lines:
            try:
                data = json.loads(line)
                if data.get("type") == "a2ui":
                    msg = data.get("message", {})
                    if "surfaceUpdate" in msg:
                        update = msg["surfaceUpdate"]
                        for comp in update.get("components", []):
                            if "x-sre-tool-log" in comp.get("component", {}):
                                tool_logs.append(comp["component"]["x-sre-tool-log"])
            except Exception:
                pass

        # Assertions
        assert len(tool_logs) >= 2, (
            "Should have at least 2 tool log events (running, completed)"
        )

        # Check first log (running)
        running_log = tool_logs[0]
        assert running_log["tool_name"] == "test_tool"
        assert running_log["status"] == "running"
        assert running_log["args"] == {"arg1": "value1"}

        # Check second log (completed)
        # Find the one with status completed (iteration order in list might correspond to emission)
        completed_log = next(
            (log for log in tool_logs if log["status"] == "completed"), None
        )
        assert completed_log is not None
        assert completed_log["tool_name"] == "test_tool"
        # Server unwraps {"result": "val"} to "val"
        assert completed_log["result"] == "success"
