# 1. APPLY PATCHES AS EARLY AS POSSIBLE
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


import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.adk.cli.fast_api import get_fast_api_app

# 2. INTERNAL IMPORTS
from sre_agent.agent import root_agent
from sre_agent.tools import (
    extract_log_patterns,
    fetch_trace,
    list_log_entries,
)

app = FastAPI(title="SRE Agent Toolbox API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
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

    # Create session service
    session_service = InMemorySessionService()  # type: ignore

    # Create invocation context
    inv_ctx = InvocationContext(
        session=session,
        agent=root_agent,
        invocation_id="api-inv",
        session_service=session_service,
    )

    return ToolContext(invocation_context=inv_ctx)


# 3. TOOL ENDPOINTS


@app.get("/api/tools/trace/{trace_id}")
async def get_trace(trace_id: str, project_id: Any | None = None) -> Any:
    """Fetch and summarize a trace."""
    try:
        ctx = await get_tool_context()
        result = await fetch_trace(
            trace_id=trace_id, project_id=project_id, tool_context=ctx
        )
        return result
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/tools/logs/analyze")
async def analyze_logs(payload: dict[str, Any]) -> Any:
    """Fetch logs and extract patterns."""
    try:
        ctx = await get_tool_context()
        # 1. Fetch logs from Cloud Logging
        entries = await list_log_entries(
            filter=payload.get("filter"),
            project_id=payload.get("project_id"),
            tool_context=ctx,
        )
        # 2. Extract patterns from the fetched entries
        result = await extract_log_patterns(log_entries=entries, tool_context=ctx)
        return result
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


# 4. MOUNT ADK AGENT

# This creates the FastAPI app with /copilotkit and other routes
adk_app = get_fast_api_app(
    agents_dir="sre_agent",
    web=False,  # We don't need the internal ADK React UI
)

# Mount the ADK app into our main app
app.mount("/", adk_app)

if __name__ == "__main__":
    # Run on 8000
    print("🚀 Starting SRE Agent + Tools API on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
