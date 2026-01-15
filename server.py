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


@app.middleware("http")
async def log_requests(request: Request, call_next: Any) -> Any:
    """Middleware to log all HTTP requests."""
    logger.debug(f"👉 Request started: {request.method} {request.url}")
    try:
        response = await call_next(request)
        logger.debug(
            f"✅ Request finished: {request.method} {request.url} - Status: {response.status_code}"
        )
        return response
    except Exception as e:
        logger.error(
            f"❌ Request failed: {request.method} {request.url} - Error: {e}",
            exc_info=True,
        )
        raise


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


# 4. GENUI ENDPOINT (A2UI Protocol)


class ChatRequest(BaseModel):
    """Request model for GenUI chat."""

    messages: list[dict[str, Any]]
    project_id: str | None = None  # Optional project ID for context


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
async def genui_chat(request: ChatRequest) -> StreamingResponse:
    """Experimental GenUI endpoint.

    Receives a user message, runs logic via the SRE Agent,
    and streams back A2UI events (BeginRendering, SurfaceUpdate) + Text.
    """
    logger.info("Received GenUI chat request")
    user_message = request.messages[-1]["text"] if request.messages else ""
    project_id = request.project_id  # Extract project_id from request
    logger.info(f"Project ID from request: {project_id}")

    async def event_generator() -> AsyncGenerator[str, None]:
        import json
        import uuid

        from google.genai import types

        # Check for Remote Agent Override
        remote_agent_id = os.getenv("SRE_AGENT_ID")

        if remote_agent_id:
            logger.info(f"Using Remote Agent: {remote_agent_id}")
            try:
                from vertexai.preview import reasoning_engines

                # Instantiate remote agent
                remote_agent = reasoning_engines.ReasoningEngine(remote_agent_id)

                # Query the remote agent
                # Note: This is currently synchronous/blocking in the thread, effectively.
                # Ideally we offload to threadpool but for simplicity:
                response = remote_agent.query(input=user_message)  # type: ignore[attr-defined]

                # The response from AdkApp/ReasoningEngine is typically just the text content if not structured.
                # If we lose events, we just stream the text.
                if response:
                    yield json.dumps({"type": "text", "content": str(response)}) + "\n"

                return
            except Exception as e:
                logger.error(f"Remote Agent Error: {e}", exc_info=True)
                yield (
                    json.dumps(
                        {
                            "type": "text",
                            "content": f"Error communicating with remote agent: {e}",
                        }
                    )
                    + "\n"
                )
                return

        # 1. Setup Context
        tool_ctx = await get_tool_context()
        # Access protected member as it is not exposed publicly
        inv_ctx = tool_ctx._invocation_context

        # Set user content
        logger.info(f"Setting user_content with message: '{user_message}'")
        inv_ctx.user_content = types.Content(
            role="user", parts=[types.Part(text=user_message)]
        )

        logger.info(f"inv_ctx.user_content: {inv_ctx.user_content}")

        # WORKAROUND: Inject user message into system instruction
        # adk-py 0.1.0 LlmAgent seems to ignore user_content in stateless (single-turn) runs.
        # We clone the agent and append the user message to the instruction to ensure it's seen.
        if user_message or project_id:
            # properly clone the agent
            cloned_agent = root_agent.clone()
            if isinstance(cloned_agent.instruction, str):
                # Add project context if provided
                if project_id:
                    cloned_agent.instruction += (
                        f"\n\nIMPORTANT PROJECT CONTEXT: The user has selected project '{project_id}'. "
                        "Use this project_id for all tool calls that require a project_id parameter. "
                        "Do not ask the user which project to use - always use this selected project."
                    )

                # Add user message
                if user_message:
                    cloned_agent.instruction += (
                        f"\n\nIMPORTANT: The user just said: '{user_message}'. "
                        "Respond to this request immediately. Do not greet the user again."
                    )
            inv_ctx.agent = cloned_agent

        # Track surfaces to avoid duplicate beginRendering
        # Map tool_name -> {'surface_id': str, 'args': dict}
        active_tools: dict[str, dict[str, Any]] = {}

        # 2. Run Agent
        # Use the agent from the context (which might be the cloned one)
        try:
            agent_to_run = inv_ctx.agent or root_agent
            async for event in agent_to_run.run_async(inv_ctx):
                if not event.content or not event.content.parts:
                    continue

                for part in event.content.parts:
                    # Handle Text
                    if part.text:
                        yield json.dumps({"type": "text", "content": part.text}) + "\n"

                    # Handle Tool Calls (Begin Rendering Tool Log)
                    if part.function_call:
                        fc = part.function_call
                        tool_name = fc.name
                        if not tool_name:
                            continue
                        args = fc.args

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
                        formatted_result: Any = ""

                        if isinstance(result, dict):
                            if "error" in result:
                                status = "error"
                                formatted_result = result["error"]
                                # Include error type for better debugging
                                if "error_type" in result:
                                    formatted_result = (
                                        f"[{result['error_type']}] {formatted_result}"
                                    )
                                # Log non-retryable errors for debugging
                                if result.get("non_retryable"):
                                    logger.warning(
                                        f"Non-retryable error for {tool_name}: {result.get('error_type', 'UNKNOWN')}"
                                    )
                            elif "warning" in result:
                                # Status remains completed (success) but we highlight the warning
                                formatted_result = f"WARNING: {result['warning']}"
                                # Include error type in warning if available
                                if "error_type" in result:
                                    formatted_result = (
                                        f"[{result['error_type']}] {formatted_result}"
                                    )
                            elif "result" in result:
                                formatted_result = result["result"]
                            else:
                                formatted_result = result

                            # Flatten remaining dict if not unwrapped
                            if isinstance(formatted_result, dict):
                                formatted_result = str(formatted_result)
                        else:
                            formatted_result = str(result)

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
                                "result": str(
                                    formatted_result
                                ),  # Serialize result for log
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
            yield (
                json.dumps({"type": "text", "content": f"An error occurred: {e!s}"})
                + "\n"
            )
        finally:
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
