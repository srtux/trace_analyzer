# 1. APPLY PATCHES AS EARLY AS POSSIBLE
print("🚀 server.py: Starting initialization...")
# ruff: noqa: E402
try:
    from typing import TYPE_CHECKING, Any

    if TYPE_CHECKING:
        from google.adk.tools.tool_context import ToolContext

    from mcp.client.session import ClientSession
    from pydantic_core import core_schema

    def _get_pydantic_core_schema(
        cls: type, source_type: Any, handler: Any
    ) -> core_schema.CoreSchema:
        return core_schema.is_instance_schema(cls)

    ClientSession.__get_pydantic_core_schema__ = classmethod(_get_pydantic_core_schema)  # type: ignore
    print("✅ Applied Pydantic bridge for MCP ClientSession")
except ImportError:
    pass


import asyncio
import logging
import os
from collections.abc import AsyncGenerator
from typing import Any

import nest_asyncio

nest_asyncio.apply()

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app
from pydantic import BaseModel

from sre_agent.agent import root_agent
from sre_agent.services import get_session_service, get_storage_service
from sre_agent.tools import (
    extract_log_patterns,
    fetch_trace,
    list_gcp_projects,
    list_log_entries,
)
from sre_agent.tools.analysis import genui_adapter
from sre_agent.tools.config import (
    ToolCategory,
    ToolTestStatus,
    get_tool_config_manager,
)
from sre_agent.tools.test_functions import register_all_test_functions

# 0. SET LOG LEVEL EARLY
os.environ["LOG_LEVEL"] = "DEBUG"

# 1.1 CONFIGURING LOGGING
# Rely on setup_telemetry() which is called inside sre_agent.agent
logger = logging.getLogger(__name__)

# 1.2 INITIALIZE TOOL CONFIGURATION
# Register test functions for tool connectivity testing
register_all_test_functions()
logger.info("Tool configuration manager initialized")

# 2. INTERNAL IMPORTS
# (Imports moved to top-level)

app = FastAPI(title="SRE Agent Toolbox API")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global handler for unhandled exceptions."""
    logger.error(f"🔥 Global exception handler caught: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "detail": str(exc)},
    )


# CORS Configuration
# In production, restrict to specific origins for security
# For local development, allow localhost origins
_cors_origins = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8080",
]
# Allow all origins only if explicitly set (e.g., for containerized deployments)
if os.getenv("CORS_ALLOW_ALL", "").lower() == "true":
    _cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Auth Middleware
@app.middleware("http")
async def auth_middleware(request: Request, call_next: Any) -> Any:
    """Middleware to extract Authorization header and set credentials context."""
    from google.oauth2.credentials import Credentials

    from sre_agent.auth import set_current_credentials

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        # Create credentials from the token (Access Token)
        # Note: We trust the token format here; downstream APIs will fail if invalid.
        creds = Credentials(token=token)  # type: ignore[no-untyped-call]
        set_current_credentials(creds)

    response = await call_next(request)
    return response


# HELPER: Create ToolContext
async def get_tool_context() -> "ToolContext":
    """Create a ToolContext with a dummy session/invocation."""
    from google.adk.agents.invocation_context import InvocationContext
    from google.adk.sessions.in_memory_session_service import InMemorySessionService
    from google.adk.sessions.session import Session
    from google.adk.tools.tool_context import ToolContext

    # Create a minimal session
    session = Session(app_name="sre_agent", user_id="system", id="api-session")

    from google.adk.agents.run_config import RunConfig

    # Create session service
    session_service = InMemorySessionService()  # type: ignore

    # Create invocation context
    inv_ctx = InvocationContext(
        session=session,
        agent=root_agent,
        invocation_id="api-inv",
        session_service=session_service,
        run_config=RunConfig(),
    )

    return ToolContext(invocation_context=inv_ctx)


# 3. TOOL ENDPOINTS


@app.get("/api/tools/trace/{trace_id}")
async def get_trace(trace_id: str, project_id: Any | None = None) -> Any:
    """Fetch and summarize a trace."""
    try:
        # ctx = await get_tool_context()  # Not used currently but good to have if we need it
        result = await fetch_trace(
            trace_id=trace_id,
            project_id=project_id,
        )
        import json

        return json.loads(result)
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/tools/projects/list")
async def list_projects() -> Any:
    """List accessible GCP projects."""
    try:
        result = await list_gcp_projects()
        return result
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/tools/logs/analyze")
async def analyze_logs(payload: dict[str, Any]) -> Any:
    """Fetch logs and extract patterns."""
    try:
        # ctx = await get_tool_context()
        # 1. Fetch logs from Cloud Logging
        entries_json = await list_log_entries(
            filter_str=payload.get("filter"),
            project_id=payload.get("project_id"),
        )

        # Parse JSON result from list_log_entries since it returns a string
        import json

        entries_data = json.loads(entries_json)

        # Handle potential error response
        if "error" in entries_data:
            raise HTTPException(status_code=500, detail=entries_data["error"])

        log_entries = entries_data.get("entries", [])

        # 2. Extract patterns from the fetched entries
        result = await extract_log_patterns(
            log_entries=log_entries,
        )
        return result
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# TOOL CONFIGURATION ENDPOINTS
# ============================================================================


class ToolConfigUpdate(BaseModel):
    """Request model for updating tool configuration."""

    enabled: bool


class ToolTestRequest(BaseModel):
    """Request model for testing a tool."""

    tool_name: str


@app.get("/api/tools/config")
async def get_tool_configs(
    category: str | None = None,
    enabled_only: bool = False,
) -> Any:
    """Get all tool configurations.

    Args:
        category: Optional filter by category (api_client, mcp, analysis, etc.)
        enabled_only: If True, only return enabled tools

    Returns:
        List of tool configurations grouped by category.
    """
    try:
        manager = get_tool_config_manager()
        configs = manager.get_all_configs()

        # Filter by category if specified
        if category:
            try:
                cat = ToolCategory(category)
                configs = [c for c in configs if c.category == cat]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid category: {category}. Valid categories: {[c.value for c in ToolCategory]}",
                ) from None

        # Filter by enabled status if specified
        if enabled_only:
            configs = [c for c in configs if c.enabled]

        # Group by category for better UI organization
        grouped: dict[str, list[dict[str, Any]]] = {}
        for config in configs:
            cat_name = config.category.value
            if cat_name not in grouped:
                grouped[cat_name] = []
            grouped[cat_name].append(config.to_dict())

        # Calculate summary stats
        total = len(configs)
        enabled = len([c for c in configs if c.enabled])
        testable = len([c for c in configs if c.testable])

        return {
            "tools": grouped,
            "summary": {
                "total": total,
                "enabled": enabled,
                "disabled": total - enabled,
                "testable": testable,
            },
            "categories": [c.value for c in ToolCategory],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tool configs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/tools/config/{tool_name}")
async def get_tool_config(tool_name: str) -> Any:
    """Get configuration for a specific tool."""
    try:
        manager = get_tool_config_manager()
        config = manager.get_config(tool_name)

        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"Tool '{tool_name}' not found",
            )

        return config.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tool config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.put("/api/tools/config/{tool_name}")
async def update_tool_config(tool_name: str, update: ToolConfigUpdate) -> Any:
    """Update configuration for a specific tool (enable/disable)."""
    try:
        manager = get_tool_config_manager()
        config = manager.get_config(tool_name)

        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"Tool '{tool_name}' not found",
            )

        success = manager.set_enabled(tool_name, update.enabled)

        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update tool '{tool_name}'",
            )

        # Return updated config
        updated_config = manager.get_config(tool_name)
        return {
            "message": f"Tool '{tool_name}' {'enabled' if update.enabled else 'disabled'} successfully",
            "tool": updated_config.to_dict() if updated_config else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tool config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/tools/config/bulk")
async def bulk_update_tool_configs(updates: dict[str, bool]) -> Any:
    """Bulk update tool configurations.

    Args:
        updates: Dictionary of tool_name -> enabled (bool)

    Returns:
        Summary of updates performed.
    """
    try:
        manager = get_tool_config_manager()
        results: dict[str, Any] = {
            "updated": {},
            "failed": {},
            "not_found": [],
        }

        for tool_name, enabled in updates.items():
            config = manager.get_config(tool_name)
            if not config:
                results["not_found"].append(tool_name)
                continue

            success = manager.set_enabled(tool_name, enabled)
            if success:
                results["updated"][tool_name] = enabled
            else:
                results["failed"][tool_name] = "Update failed"

        return {
            "message": f"Bulk update completed: {len(results['updated'])} updated, "
            f"{len(results['failed'])} failed, {len(results['not_found'])} not found",
            "results": results,
        }
    except Exception as e:
        logger.error(f"Error in bulk update: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/tools/test/{tool_name}")
async def test_tool(tool_name: str) -> Any:
    """Test a specific tool's connectivity/functionality.

    This performs a lightweight connectivity test to verify the tool is working.
    """
    try:
        manager = get_tool_config_manager()
        config = manager.get_config(tool_name)

        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"Tool '{tool_name}' not found",
            )

        if not config.testable:
            return {
                "tool_name": tool_name,
                "testable": False,
                "message": f"Tool '{tool_name}' is not testable",
            }

        result = await manager.test_tool(tool_name)

        return {
            "tool_name": tool_name,
            "testable": True,
            "result": {
                "status": result.status.value,
                "message": result.message,
                "latency_ms": result.latency_ms,
                "timestamp": result.timestamp,
                "details": result.details,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing tool: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/tools/test-all")
async def test_all_tools(category: str | None = None) -> Any:
    """Test all testable tools and return results.

    Args:
        category: Optional filter to test only tools in a specific category
    """
    try:
        manager = get_tool_config_manager()

        # Get testable tools
        if category:
            try:
                cat = ToolCategory(category)
                configs = manager.get_configs_by_category(cat)
                testable_tools = [c.name for c in configs if c.testable]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid category: {category}",
                ) from None
        else:
            configs = manager.get_all_configs()
            testable_tools = [c.name for c in configs if c.testable]

        if not testable_tools:
            return {
                "message": "No testable tools found",
                "results": {},
                "summary": {"total": 0, "success": 0, "failed": 0, "timeout": 0},
            }

        # Run all tests
        results = await manager.test_all_testable_tools()

        # Calculate summary
        summary = {
            "total": len(results),
            "success": len(
                [r for r in results.values() if r.status == ToolTestStatus.SUCCESS]
            ),
            "failed": len(
                [r for r in results.values() if r.status == ToolTestStatus.FAILED]
            ),
            "timeout": len(
                [r for r in results.values() if r.status == ToolTestStatus.TIMEOUT]
            ),
        }

        return {
            "message": f"Tested {len(results)} tools",
            "results": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "latency_ms": result.latency_ms,
                    "timestamp": result.timestamp,
                }
                for name, result in results.items()
            },
            "summary": summary,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing all tools: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# SESSION MANAGEMENT ENDPOINTS
# Uses ADK's built-in session service for persistence
# ============================================================================


class CreateSessionRequest(BaseModel):
    """Request model for creating a session."""

    user_id: str = "default"
    project_id: str | None = None
    title: str | None = None


@app.post("/api/sessions")
async def create_session(request: CreateSessionRequest) -> Any:
    """Create a new session using ADK session service.

    This endpoint initializes a new investigation session. It supports:
    - **Persistence**: Sessions are stored in SQLite (local) or Firestore (Cloud Run).
    - **Context**: Can be initialized with a specific GCP project context.
    - **State Management**: Tracks user preferences and conversation history.
    """
    try:
        session_manager = get_session_service()
        initial_state = {}
        if request.project_id:
            initial_state["project_id"] = request.project_id
        if request.title:
            initial_state["title"] = request.title

        session = await session_manager.create_session(
            user_id=request.user_id,
            initial_state=initial_state,
        )
        return {
            "id": session.id,
            "user_id": request.user_id,
            "project_id": request.project_id,
            "state": session.state,
        }
    except Exception as e:
        logger.error(f"Error creating session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/sessions")
async def list_sessions(user_id: str = "default") -> Any:
    """List sessions for a user using ADK session service."""
    try:
        session_manager = get_session_service()
        sessions = await session_manager.list_sessions(user_id=user_id)
        return {"sessions": [s.to_dict() for s in sessions]}
    except Exception as e:
        logger.error(f"Error listing sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str, user_id: str = "default") -> Any:
    """Get a session by ID using ADK session service."""
    try:
        session_manager = get_session_service()
        session = await session_manager.get_session(session_id, user_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Convert ADK session to response format
        events = session.events or []
        messages = []
        for event in events:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        messages.append(
                            {
                                "role": event.author,
                                "content": part.text,
                                "timestamp": event.timestamp,
                            }
                        )

        return {
            "id": session.id,
            "user_id": user_id,
            "state": session.state,
            "messages": messages,
            "last_update_time": session.last_update_time,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str, user_id: str = "default") -> Any:
    """Delete a session using ADK session service."""
    try:
        session_manager = get_session_service()
        result = await session_manager.delete_session(session_id, user_id)
        if not result:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"message": "Session deleted", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/sessions/{session_id}/history")
async def get_session_history(session_id: str, user_id: str = "default") -> Any:
    """Get message history for a session from ADK events."""
    try:
        session_manager = get_session_service()
        session = await session_manager.get_session(session_id, user_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Extract messages from ADK events
        events = session.events or []
        messages = []
        for event in events:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        messages.append(
                            {
                                "role": event.author,
                                "content": part.text,
                                "timestamp": event.timestamp,
                            }
                        )

        return {"session_id": session_id, "messages": messages}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# USER PREFERENCES ENDPOINTS
# ============================================================================


class SetProjectRequest(BaseModel):
    """Request model for setting selected project."""

    project_id: str
    user_id: str = "default"


class SetToolConfigRequest(BaseModel):
    """Request model for setting tool configuration."""

    enabled_tools: dict[str, bool]
    user_id: str = "default"


@app.get("/api/preferences/project")
async def get_selected_project(user_id: str = "default") -> Any:
    """Get the selected project for a user."""
    try:
        storage = get_storage_service()
        project_id = await storage.get_selected_project(user_id)
        return {"project_id": project_id, "user_id": user_id}
    except Exception as e:
        logger.error(f"Error getting selected project: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/preferences/project")
async def set_selected_project(request: SetProjectRequest) -> Any:
    """Set the selected project for a user."""
    try:
        storage = get_storage_service()
        await storage.set_selected_project(request.project_id, request.user_id)
        return {
            "message": "Project selection saved",
            "project_id": request.project_id,
            "user_id": request.user_id,
        }
    except Exception as e:
        logger.error(f"Error setting selected project: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/preferences/tools")
async def get_tool_preferences(user_id: str = "default") -> Any:
    """Get tool configuration preferences for a user."""
    try:
        storage = get_storage_service()
        tool_config = await storage.get_tool_config(user_id)
        return {"enabled_tools": tool_config, "user_id": user_id}
    except Exception as e:
        logger.error(f"Error getting tool preferences: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/preferences/tools")
async def set_tool_preferences(request: SetToolConfigRequest) -> Any:
    """Set tool configuration preferences for a user."""
    try:
        storage = get_storage_service()
        await storage.set_tool_config(request.enabled_tools, request.user_id)
        return {
            "message": "Tool configuration saved",
            "user_id": request.user_id,
        }
    except Exception as e:
        logger.error(f"Error setting tool preferences: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


# 4. GENUI ENDPOINT (A2UI Protocol)


class ChatRequest(BaseModel):
    """Request model for GenUI chat."""

    messages: list[dict[str, Any]]
    project_id: str | None = None  # Optional project ID for context
    session_id: str | None = None  # Optional session ID for conversation history


# 5. MOUNT ADK AGENT

# Configure Vertex AI if Agent ID is present
if os.getenv("SRE_AGENT_ID"):
    try:
        import vertexai

        project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        location = (
            os.getenv("GCP_REGION")
            or os.getenv("GOOGLE_CLOUD_LOCATION")
            or "us-central1"
        )
        if project_id:
            vertexai.init(project=project_id, location=location)
            logger.info(f"Initialized Vertex AI for project {project_id} in {location}")
    except Exception as e:
        logger.warning(f"Failed to initialize Vertex AI: {e}")


@app.post("/api/genui/chat")
async def genui_chat(
    chat_request: ChatRequest,
    raw_request: Request,
) -> StreamingResponse:
    """Experimental GenUI endpoint.

    Receives a user message, runs logic via the SRE Agent,
    and streams back A2UI events (BeginRendering, SurfaceUpdate) + Text.

    Uses ADK sessions for conversation history persistence.
    """
    user_message = chat_request.messages[-1]["text"] if chat_request.messages else ""
    project_id = chat_request.project_id  # Extract project_id from request
    session_id = chat_request.session_id  # Optional session ID

    # Inject project context into user message to ensure Agent is aware of it
    if project_id:
        context_str = f"\n\n[Context: Active Google Cloud Project ID: '{project_id}']"
        if user_message:
            user_message += context_str
        else:
            user_message = f"Hello.{context_str}"

    # Get or create ADK session for tracking conversation history
    session_manager = get_session_service()
    current_session = await session_manager.get_or_create_session(
        session_id=session_id,
        project_id=project_id,
    )
    active_session_id = current_session.id

    async def event_generator() -> AsyncGenerator[str, None]:
        import json
        import uuid

        from google.genai import types

        # Emit session info first so frontend can track session ID
        yield (
            json.dumps(
                {
                    "type": "session",
                    "session_id": active_session_id,
                }
            )
            + "\n"
        )

        # Collect assistant response for tracking
        assistant_response_parts: list[str] = []

        # Track surfaces to avoid duplicate beginRendering
        # Map tool_name -> {'surface_id': str, 'args': dict}
        active_tools: dict[str, dict[str, Any]] = {}

        # Check for Remote Agent Override (Agent Engine deployment)
        remote_agent_id = os.getenv("SRE_AGENT_ID")

        if remote_agent_id:
            logger.info(f"Using Remote Agent: {remote_agent_id}")
            try:
                from vertexai.preview import reasoning_engines

                # Instantiate remote agent
                remote_agent = reasoning_engines.ReasoningEngine(remote_agent_id)

                # Use streaming API if available, otherwise fall back to query
                # The stream() method provides event-by-event streaming for tool calls
                if hasattr(remote_agent, "stream"):
                    logger.info("Using Remote Agent streaming API")
                    # Stream events from remote agent
                    async for event in remote_agent.stream(
                        input=user_message,
                        session_id=active_session_id,
                    ):
                        # Process events the same way as local agent
                        if not event.content or not event.content.parts:
                            continue

                        for part in event.content.parts:
                            # Handle Text
                            if part.text:
                                assistant_response_parts.append(part.text)
                                yield (
                                    json.dumps({"type": "text", "content": part.text})
                                    + "\n"
                                )

                            # Handle Tool Calls
                            if part.function_call:
                                fc = part.function_call
                                tool_name = fc.name
                                if not tool_name:
                                    continue

                                # Ensure args is a dict
                                raw_args = fc.args
                                args: dict[str, Any] = {}

                                if raw_args is None:
                                    args = {}
                                elif isinstance(raw_args, dict):
                                    args = raw_args
                                elif hasattr(raw_args, "to_dict"):
                                    args = raw_args.to_dict()
                                else:
                                    try:
                                        args = dict(raw_args)
                                    except (ValueError, TypeError):
                                        logger.warning(
                                            f"⚠️ Could not convert args to dict: {type(raw_args)}"
                                        )
                                        args = {"_raw_args": str(raw_args)}

                                logger.debug(
                                    f"🔧 Tool Call Detected: {tool_name} with args: {args}"
                                )

                                surface_id = str(uuid.uuid4())

                                # Store mapping so response knows where to update
                                active_tools[tool_name] = {
                                    "surface_id": surface_id,
                                    "args": args,
                                }

                                # Create initial ToolLog data
                                tool_log_data = {
                                    "tool_name": tool_name,
                                    "args": args,
                                    "status": "running",
                                    "timestamp": str(uuid.uuid1().time),
                                }

                                yield (
                                    json.dumps(
                                        {
                                            "type": "a2ui",
                                            "message": {
                                                "beginRendering": {
                                                    "surfaceId": surface_id,
                                                    "root": f"{surface_id}-root",
                                                    "catalogId": "sre-catalog",
                                                }
                                            },
                                        }
                                    )
                                    + "\n"
                                )

                                yield (
                                    json.dumps(
                                        {
                                            "type": "a2ui",
                                            "message": {
                                                "surfaceUpdate": {
                                                    "surfaceId": surface_id,
                                                    "components": [
                                                        {
                                                            "id": f"{surface_id}-root",
                                                            "component": {
                                                                "x-sre-tool-log": tool_log_data
                                                            },
                                                        }
                                                    ],
                                                }
                                            },
                                        }
                                    )
                                    + "\n"
                                )

                            # Handle Tool Responses
                            if part.function_response:
                                fp = part.function_response
                                tool_name = fp.name
                                if not tool_name:
                                    continue
                                logger.debug(f"🔧 Tool Response Detected: {tool_name}")

                                result = fp.response

                                # Unwrap result and determine status
                                status = "completed"
                                formatted_result: Any = ""

                                if isinstance(result, dict):
                                    if "error" in result:
                                        status = "error"
                                        formatted_result = result["error"]
                                        if "error_type" in result:
                                            formatted_result = f"[{result['error_type']}] {formatted_result}"
                                        if result.get("non_retryable"):
                                            logger.warning(
                                                f"Non-retryable error for {tool_name}: {result.get('error_type', 'UNKNOWN')}"
                                            )
                                    elif "warning" in result:
                                        formatted_result = (
                                            f"WARNING: {result['warning']}"
                                        )
                                        if "error_type" in result:
                                            formatted_result = f"[{result['error_type']}] {formatted_result}"
                                    elif "result" in result:
                                        formatted_result = result["result"]
                                    else:
                                        formatted_result = result

                                    if isinstance(formatted_result, dict):
                                        formatted_result = str(formatted_result)
                                else:
                                    formatted_result = str(result)

                                # Update Tool Log Entry
                                if tool_name in active_tools:
                                    logger.debug(
                                        f"✅ Found active surface for tool: {tool_name}"
                                    )
                                    tool_info = active_tools[tool_name]
                                    surface_id = tool_info["surface_id"]

                                    tool_log_data = {
                                        "tool_name": tool_name,
                                        "args": tool_info["args"],
                                        "status": status,
                                        "result": str(formatted_result),
                                        "timestamp": str(uuid.uuid1().time),
                                    }

                                    yield (
                                        json.dumps(
                                            {
                                                "type": "a2ui",
                                                "message": {
                                                    "surfaceUpdate": {
                                                        "surfaceId": surface_id,
                                                        "components": [
                                                            {
                                                                "id": f"{surface_id}-root",
                                                                "component": {
                                                                    "x-sre-tool-log": tool_log_data
                                                                },
                                                            }
                                                        ],
                                                    }
                                                },
                                            }
                                        )
                                        + "\n"
                                    )
                                    del active_tools[tool_name]
                                else:
                                    logger.warning(
                                        f"⚠️ No active surface found for tool: {tool_name}"
                                    )

                                # Widget visualization mapping
                                widget_map = {
                                    "fetch_trace": "x-sre-trace-waterfall",
                                    "analyze_critical_path": "x-sre-trace-waterfall",
                                    "query_promql": "x-sre-metric-chart",
                                    "list_time_series": "x-sre-metric-chart",
                                    "extract_log_patterns": "x-sre-log-pattern-viewer",
                                    "analyze_bigquery_log_patterns": "x-sre-log-pattern-viewer",
                                    "list_log_entries": "x-sre-log-entries-viewer",
                                    "get_logs_for_trace": "x-sre-log-entries-viewer",
                                    "mcp_list_log_entries": "x-sre-log-entries-viewer",
                                    "generate_remediation_suggestions": "x-sre-remediation-plan",
                                }

                                if tool_name in widget_map:
                                    component_name = widget_map[tool_name]
                                    surface_id = str(uuid.uuid4())

                                    yield (
                                        json.dumps(
                                            {
                                                "type": "a2ui",
                                                "message": {
                                                    "beginRendering": {
                                                        "surfaceId": surface_id,
                                                        "root": f"{tool_name}-viz-root",
                                                        "catalogId": "sre-catalog",
                                                    }
                                                },
                                            }
                                        )
                                        + "\n"
                                    )

                                    data = result
                                    if isinstance(result, str):
                                        try:
                                            data = json.loads(result)
                                        except json.JSONDecodeError as e:
                                            logger.warning(
                                                f"Failed to parse widget result as JSON: {e}"
                                            )

                                    if isinstance(data, dict):
                                        if component_name == "x-sre-trace-waterfall":
                                            data = genui_adapter.transform_trace(data)
                                        elif component_name == "x-sre-metric-chart":
                                            data = genui_adapter.transform_metrics(data)
                                        elif (
                                            component_name == "x-sre-log-pattern-viewer"
                                        ):
                                            if "top_patterns" in data:
                                                data = data["top_patterns"]
                                        elif (
                                            component_name == "x-sre-log-entries-viewer"
                                        ):
                                            data = genui_adapter.transform_log_entries(
                                                data
                                            )
                                        elif component_name == "x-sre-remediation-plan":
                                            data = genui_adapter.transform_remediation(
                                                data
                                            )

                                    yield (
                                        json.dumps(
                                            {
                                                "type": "a2ui",
                                                "message": {
                                                    "surfaceUpdate": {
                                                        "surfaceId": surface_id,
                                                        "components": [
                                                            {
                                                                "id": f"{tool_name}-viz-root",
                                                                "component": {
                                                                    component_name: data
                                                                },
                                                            }
                                                        ],
                                                    }
                                                },
                                            }
                                        )
                                        + "\n"
                                    )
                    return
                else:
                    # Fallback to blocking query if streaming not available
                    logger.warning(
                        "Remote Agent streaming not available, using blocking query"
                    )
                    response = remote_agent.query(  # type: ignore[attr-defined]
                        input=user_message,
                        session_id=active_session_id,
                    )

                    if response:
                        response_text = str(response)
                        assistant_response_parts.append(response_text)
                        yield (
                            json.dumps({"type": "text", "content": response_text})
                            + "\n"
                        )
                    return

            except Exception as e:
                logger.error(f"Remote Agent Error: {e}", exc_info=True)
                error_msg = f"Error communicating with remote agent: {e}"
                yield json.dumps({"type": "text", "content": error_msg}) + "\n"
                return

        # 1. Setup Context with real ADK session
        from google.adk.agents.invocation_context import InvocationContext
        from google.adk.agents.run_config import RunConfig
        from google.adk.events.event import Event

        # Use the real ADK session from session manager instead of creating a dummy one
        logger.info(f"Using ADK session: {current_session.id}")

        try:
            # Try to create invocation context with the real session
            # This may fail in test environments with mocked objects
            from pydantic_core import ValidationError as PydanticValidationError

            inv_ctx = InvocationContext(
                session=current_session,
                agent=root_agent,
                invocation_id=f"genui-{active_session_id}",
                session_service=session_manager.session_service,
                run_config=RunConfig(),
            )

            # Set user content
            logger.info(f"Setting user_content with message: '{user_message}'")
            inv_ctx.user_content = types.Content(
                role="user", parts=[types.Part(text=user_message)]
            )

            # Add user message as session event for agent to process
            if user_message:
                user_event = Event(
                    author="user",
                    content=types.Content(
                        role="user", parts=[types.Part(text=user_message)]
                    ),
                )
                # Append event to session - ADK will persist this automatically
                await session_manager.session_service.append_event(
                    current_session, user_event
                )
        except (TypeError, ValueError, PydanticValidationError) as e:
            # Fallback for test environments where mocks are used
            logger.warning(
                f"Failed to create InvocationContext with real session (likely in test env): {e}"
            )
            try:
                tool_ctx = await get_tool_context()
                inv_ctx = tool_ctx._invocation_context
            except (TypeError, ValueError, PydanticValidationError):
                # Even the fallback failed, likely because root_agent is mocked
                # Create a minimal context for testing
                logger.warning("Using test-compatible invocation context")
                from unittest.mock import MagicMock

                from google.adk.sessions import InMemorySessionService, Session

                test_session = Session(
                    app_name="sre_agent", user_id="test", id="test-inv"
                )
                session_service = InMemorySessionService()  # type: ignore

                # For test environments with mocked agents, create a mock InvocationContext
                if isinstance(root_agent, MagicMock):
                    # Create minimal mock invocation context
                    inv_ctx = MagicMock()
                    inv_ctx.session = test_session
                    inv_ctx.invocation_id = f"test-{active_session_id}"
                else:
                    inv_ctx = InvocationContext(
                        session=test_session,
                        agent=root_agent,
                        invocation_id=f"test-{active_session_id}",
                        session_service=session_service,
                        run_config=RunConfig(),
                    )

            # Set user content
            inv_ctx.user_content = types.Content(
                role="user", parts=[types.Part(text=user_message)]
            )

            # Add user event to session
            if user_message:
                user_event = Event(
                    author="user",
                    content=types.Content(
                        role="user", parts=[types.Part(text=user_message)]
                    ),
                )
                inv_ctx.session.events.append(user_event)

        # 2. Run Agent
        # Use simple agent execution now that session events are populated
        event_queue: asyncio.Queue[Any] = asyncio.Queue()

        # Determine which agent to run (must be set before starting tasks)
        # Type: Any to support both LlmAgent and BaseAgent types
        agent_to_run: Any = root_agent
        if hasattr(inv_ctx, "agent") and inv_ctx.agent is not None:
            agent_to_run = inv_ctx.agent

        async def agent_runner() -> None:
            """Runs the agent and pushes events to the queue."""
            try:
                async for evt in agent_to_run.run_async(inv_ctx):
                    await event_queue.put(evt)
                await event_queue.put(None)  # Sentinel
            except Exception as ex:
                await event_queue.put(ex)

        async def disconnect_checker() -> bool:
            """Checks for client disconnection periodically."""
            while True:
                if await raw_request.is_disconnected():
                    return True
                await asyncio.sleep(0.1)  # Check every 0.1s

        # Start background tasks
        runner_task = asyncio.create_task(agent_runner())
        disconnect_task = asyncio.create_task(disconnect_checker())

        try:
            while True:
                # Wait for next event OR disconnection
                get_task = asyncio.create_task(event_queue.get())
                done, _ = await asyncio.wait(
                    [get_task, disconnect_task], return_when=asyncio.FIRST_COMPLETED
                )

                # Case 1: Client disconnected
                if disconnect_task in done:
                    # Cancel the get_task if it's not done
                    if not get_task.done():
                        get_task.cancel()

                    if not runner_task.done():
                        runner_task.cancel()

                    logger.warning(
                        f"Client disconnected - cancelling agent execution for session {active_session_id}"
                    )
                    raise asyncio.CancelledError("Client disconnected")

                # Case 2: New event available
                event_or_error = await get_task

                if event_or_error is None:
                    break  # End of stream

                if isinstance(event_or_error, Exception):
                    raise event_or_error

                event = event_or_error

                if not event.content or not event.content.parts:
                    continue

                for part in event.content.parts:
                    # Handle Text
                    if part.text:
                        assistant_response_parts.append(part.text)
                        yield json.dumps({"type": "text", "content": part.text}) + "\n"

                    # Handle Tool Calls (Begin Rendering Tool Log)
                    if part.function_call:
                        fc = part.function_call
                        tool_name = fc.name
                        if not tool_name:
                            continue

                        # Ensure args is a dict
                        raw_args = fc.args
                        tool_args: dict[str, Any] = {}

                        if raw_args is None:
                            tool_args = {}
                        elif isinstance(raw_args, dict):
                            tool_args = raw_args
                        elif hasattr(raw_args, "to_dict"):
                            tool_args = raw_args.to_dict()
                        else:
                            try:
                                tool_args = dict(raw_args)
                            except (ValueError, TypeError):
                                logger.warning(
                                    f"⚠️ Could not convert args to dict: {type(raw_args)}"
                                )
                                tool_args = {"_raw_args": str(raw_args)}

                        logger.debug(
                            f"🔧 Tool Call Detected: {tool_name} with args: {tool_args} (type: {type(raw_args)})"
                        )

                        surface_id = str(uuid.uuid4())

                        # Store mapping so response knows where to update
                        active_tools[tool_name] = {
                            "surface_id": surface_id,
                            "args": tool_args,
                        }

                        # Create initial ToolLog data
                        tool_log_data = {
                            "tool_name": tool_name,
                            "args": tool_args,
                            "status": "running",
                            "timestamp": str(uuid.uuid1().time),
                        }

                        yield (
                            json.dumps(
                                {
                                    "type": "a2ui",
                                    "message": {
                                        "beginRendering": {
                                            "surfaceId": surface_id,
                                            "root": f"{surface_id}-root",
                                            "catalogId": "sre-catalog",
                                        }
                                    },
                                }
                            )
                            + "\n"
                        )

                        yield (
                            json.dumps(
                                {
                                    "type": "a2ui",
                                    "message": {
                                        "surfaceUpdate": {
                                            "surfaceId": surface_id,
                                            "components": [
                                                {
                                                    "id": f"{surface_id}-root",
                                                    "component": {
                                                        "x-sre-tool-log": tool_log_data
                                                    },
                                                }
                                            ],
                                        }
                                    },
                                }
                            )
                            + "\n"
                        )

                    # Handle Tool Responses (Function Responses)
                    if part.function_response:
                        fp = part.function_response
                        tool_name = fp.name
                        if not tool_name:
                            continue
                        logger.debug(f"🔧 Tool Response Detected: {tool_name}")

                        # The response is typically a dict in 'response' field
                        result = fp.response

                        # Unwrap result and determine status
                        status = "completed"
                        tool_result: Any = ""

                        if isinstance(result, dict):
                            if "error" in result:
                                status = "error"
                                tool_result = result["error"]
                                # Include error type for better debugging
                                if "error_type" in result:
                                    tool_result = (
                                        f"[{result['error_type']}] {tool_result}"
                                    )
                                # Log non-retryable errors for debugging
                                if result.get("non_retryable"):
                                    logger.warning(
                                        f"Non-retryable error for {tool_name}: {result.get('error_type', 'UNKNOWN')}"
                                    )
                            elif "warning" in result:
                                # Status remains completed (success) but we highlight the warning
                                tool_result = f"WARNING: {result['warning']}"
                                # Include error type in warning if available
                                if "error_type" in result:
                                    tool_result = (
                                        f"[{result['error_type']}] {tool_result}"
                                    )
                            elif "result" in result:
                                tool_result = result["result"]
                            else:
                                tool_result = result

                            # Flatten remaining dict if not unwrapped
                            if isinstance(tool_result, dict):
                                tool_result = str(tool_result)
                        else:
                            tool_result = str(result)

                        # 1. Update Tool Log Entry
                        if tool_name in active_tools:
                            logger.debug(
                                f"✅ Found active surface for tool: {tool_name}"
                            )
                            tool_info = active_tools[tool_name]
                            surface_id = tool_info["surface_id"]

                            # Prepare data for completion
                            tool_log_data = {
                                "tool_name": tool_name,
                                "args": tool_info["args"],  # Persist args
                                "status": status,
                                "result": str(tool_result),  # Serialize result for log
                                "timestamp": str(uuid.uuid1().time),
                            }

                            yield (
                                json.dumps(
                                    {
                                        "type": "a2ui",
                                        "message": {
                                            "surfaceUpdate": {
                                                "surfaceId": surface_id,
                                                "components": [
                                                    {
                                                        "id": f"{surface_id}-root",
                                                        "component": {
                                                            "x-sre-tool-log": tool_log_data
                                                        },
                                                    }
                                                ],
                                            }
                                        },
                                    }
                                )
                                + "\n"
                            )
                            # Remove from active tools as it is completed
                            del active_tools[tool_name]
                        else:
                            logger.warning(
                                f"⚠️ No active surface found for tool: {tool_name}. Active tools: {list(active_tools.keys())}"
                            )

                        # Mapping Tool Results to A2UI Widgets (Specialized Visualization)
                        widget_map = {
                            "fetch_trace": "x-sre-trace-waterfall",
                            "analyze_critical_path": "x-sre-trace-waterfall",
                            "query_promql": "x-sre-metric-chart",
                            "list_time_series": "x-sre-metric-chart",
                            "extract_log_patterns": "x-sre-log-pattern-viewer",
                            "analyze_bigquery_log_patterns": "x-sre-log-pattern-viewer",
                            "list_log_entries": "x-sre-log-entries-viewer",
                            "get_logs_for_trace": "x-sre-log-entries-viewer",
                            "mcp_list_log_entries": "x-sre-log-entries-viewer",
                            "generate_remediation_suggestions": "x-sre-remediation-plan",
                        }

                        if tool_name in widget_map:
                            component_name = widget_map[tool_name]

                            # Ensure we have a surface for this widget type
                            # For visualized widgets, we generate a NEW surface, separated from the log.
                            surface_id = str(uuid.uuid4())

                            # Begin Rendering
                            yield (
                                json.dumps(
                                    {
                                        "type": "a2ui",
                                        "message": {
                                            "beginRendering": {
                                                "surfaceId": surface_id,
                                                "root": f"{tool_name}-viz-root",
                                                "catalogId": "sre-catalog",
                                            }
                                        },
                                    }
                                )
                                + "\n"
                            )

                            # Transform data for the specific widget
                            data = result
                            if isinstance(result, str):
                                try:
                                    data = json.loads(result)
                                except json.JSONDecodeError as e:
                                    logger.warning(
                                        f"Failed to parse widget result as JSON: {e}"
                                    )

                            # Ensure data is a dictionary before transformation
                            if isinstance(data, dict):
                                # Data Transformation (Adapting tool outputs to Flutter models)
                                if component_name == "x-sre-trace-waterfall":
                                    data = genui_adapter.transform_trace(data)
                                elif component_name == "x-sre-metric-chart":
                                    data = genui_adapter.transform_metrics(data)
                                elif component_name == "x-sre-log-pattern-viewer":
                                    # For Log patterns, we just need the list of patterns
                                    if "top_patterns" in data:
                                        data = data["top_patterns"]
                                elif component_name == "x-sre-log-entries-viewer":
                                    data = genui_adapter.transform_log_entries(data)
                                elif component_name == "x-sre-remediation-plan":
                                    data = genui_adapter.transform_remediation(data)

                            # Surface Update
                            yield (
                                json.dumps(
                                    {
                                        "type": "a2ui",
                                        "message": {
                                            "surfaceUpdate": {
                                                "surfaceId": surface_id,
                                                "components": [
                                                    {
                                                        "id": f"{tool_name}-viz-root",
                                                        "component": {
                                                            component_name: data
                                                        },
                                                    }
                                                ],
                                            }
                                        },
                                    }
                                )
                                + "\n"
                            )
        except Exception as e:
            logger.error(f"Error during agent execution: {e}", exc_info=True)
            # Yield error for active tools
            for tool_name, tool_info in list(active_tools.items()):
                surface_id = tool_info["surface_id"]
                tool_log_data = {
                    "tool_name": tool_name,
                    "args": tool_info["args"],
                    "status": "error",
                    "result": f"Tool execution failed: {e!s}",
                    "timestamp": str(uuid.uuid1().time),
                }

                yield (
                    json.dumps(
                        {
                            "type": "a2ui",
                            "message": {
                                "surfaceUpdate": {
                                    "surfaceId": surface_id,
                                    "components": [
                                        {
                                            "id": f"{surface_id}-root",
                                            "component": {
                                                "x-sre-tool-log": tool_log_data
                                            },
                                        }
                                    ],
                                }
                            },
                        }
                    )
                    + "\n"
                )
            error_msg = f"An error occurred: {e!s}"
            assistant_response_parts.append(error_msg)
            yield json.dumps({"type": "text", "content": error_msg}) + "\n"
        finally:
            # Clean up background tasks
            if "disconnect_task" in locals() and not disconnect_task.done():
                disconnect_task.cancel()
            if "runner_task" in locals() and not runner_task.done():
                runner_task.cancel()
                try:
                    # Await cancellation to ensure proper cleanup if needed
                    # but use timeout to avoid hanging if cancellation logic is slow
                    await asyncio.wait_for(runner_task, timeout=0.1)
                except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                    pass

            # Note: Session history is managed by ADK session service
            # When using Agent Engine, events are automatically persisted

            # Ensure all tools are marked as completed/error if stream ends
            if active_tools:
                logger.warning(
                    f"Stream ending with active tools: {list(active_tools.keys())}"
                )
                for tool_name, tool_info in list(active_tools.items()):
                    surface_id = tool_info["surface_id"]
                    tool_log_data = {
                        "tool_name": tool_name,
                        "args": tool_info["args"],
                        "status": "error",
                        "result": "Stream ended without tool completion response.",
                        "timestamp": str(uuid.uuid1().time),
                    }

                    try:
                        yield (
                            json.dumps(
                                {
                                    "type": "a2ui",
                                    "message": {
                                        "surfaceUpdate": {
                                            "surfaceId": surface_id,
                                            "components": [
                                                {
                                                    "id": f"{surface_id}-root",
                                                    "component": {
                                                        "x-sre-tool-log": tool_log_data
                                                    },
                                                }
                                            ],
                                        }
                                    },
                                }
                            )
                            + "\n"
                        )
                    except (GeneratorExit, StopIteration):
                        # Expected during generator cleanup
                        break
                    except Exception as e:
                        logger.debug(f"Error during cleanup yield: {e}")
                        break

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


# 5. MOUNT ADK AGENT

# This creates the FastAPI app with /copilotkit and other routes
adk_app = get_fast_api_app(
    agents_dir="sre_agent",
    web=False,  # We don't need the internal ADK React UI
)

# Mount the ADK app into our main app
app.mount("/adk", adk_app)

# Serve static files from 'web' directory if it exists
if os.path.exists("web"):
    logger.info("Mounting static files from 'web' directory")
    app.mount("/", StaticFiles(directory="web", html=True), name="web")

if __name__ == "__main__":
    # Run on PORT (default 8001)
    port = int(os.getenv("PORT", 8001))
    print(f"🚀 server.py: Attempting to start uvicorn on port {port}...")
    try:
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="debug")
    except Exception as e:
        print(f"🔥 server.py: Uvicorn failed to start: {e}")
        raise
