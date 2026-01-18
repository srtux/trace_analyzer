import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

# Ensure we can import server
sys.path.append(os.getcwd())


class TestStopButtonCancellation(unittest.IsolatedAsyncioTestCase):
    async def test_backend_cancellation(self):
        """
        Verify that:
        1. genui_chat starts a stream.
        2. When raw_request.is_disconnected() returns True, the agent loop is cancelled.
        """
        from starlette.requests import Request

        from server import ChatRequest, genui_chat

        # Mock Request
        mock_raw_request = MagicMock(spec=Request)
        mock_raw_request.is_disconnected = AsyncMock(return_value=False)

        # Mock Session Service
        with (
            unittest.mock.patch(
                "server.get_session_service"
            ) as mock_get_session_service,
            unittest.mock.patch("server.root_agent") as mock_root_agent,
            unittest.mock.patch("server.get_tool_context") as mock_get_tool_context,
        ):
            # Setup Session
            mock_session = MagicMock()
            mock_session.id = "test-session-id"
            mock_session.events = []
            mock_session_service = AsyncMock()
            mock_session_service.get_or_create_session.return_value = mock_session
            mock_get_session_service.return_value = mock_session_service

            # Setup Tool Context
            mock_tool_ctx = MagicMock()
            mock_inv_ctx = MagicMock()
            # CRITICAL: Set agent to None so server.py uses root_agent (our mock)
            # instead of the mock_inv_ctx.agent default mock
            mock_inv_ctx.agent = None
            mock_tool_ctx._invocation_context = mock_inv_ctx
            mock_get_tool_context.return_value = mock_tool_ctx

            # --- AGENT MOCK ---
            agent_cancelled_event = asyncio.Event()

            async def slow_agent_run(inv_ctx):
                try:
                    while True:
                        yield MagicMock()
                        # Sleep long enough to allow disconnect_checker (which sleeps 0.1s)
                        # to run and detect disconnection.
                        await asyncio.sleep(0.5)
                except asyncio.CancelledError:
                    agent_cancelled_event.set()
                    raise

            mock_root_agent.run_async = slow_agent_run

            # --- REQUEST MOCK ---
            chat_req = ChatRequest(
                messages=[{"role": "user", "text": "start"}], project_id="p"
            )

            # --- CLIENT DISCONNECT SIMULATION ---
            # Return False a few times, then True to simulate disconnect
            is_disconnected_responses = [False, False, True]

            async def side_effect_is_disconnected():
                if is_disconnected_responses:
                    return is_disconnected_responses.pop(0)
                return True

            mock_raw_request.is_disconnected.side_effect = side_effect_is_disconnected

            # Call Endpoint
            response = await genui_chat(chat_req, mock_raw_request)
            iterator = response.body_iterator

            # Consume stream
            try:
                async for _item in iterator:
                    # Force yield to event loop to allow background tasks to run
                    await asyncio.sleep(0)
                    pass
            except asyncio.CancelledError:
                pass
            except Exception as e:
                # server.py handles internal exceptions, but CancelledError is re-raised
                if "Client disconnected" not in str(e):
                    print(f"Unexpected exception during stream consumption: {e}")

            # Verify Agent Cancellation
            try:
                await asyncio.wait_for(agent_cancelled_event.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.fail("FAILURE: Agent task was NOT cancelled within timeout.")


if __name__ == "__main__":
    unittest.main()
