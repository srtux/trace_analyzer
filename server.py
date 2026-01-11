# 1. APPLY PATCHES AS EARLY AS POSSIBLE
try:
    from typing import Any

    from mcp.client.session import ClientSession
    from pydantic_core import core_schema

    def _get_pydantic_core_schema(
        cls: type, source_type: Any, handler: Any
    ) -> core_schema.CoreSchema:
        return core_schema.is_instance_schema(cls)

    ClientSession.__get_pydantic_core_schema__ = classmethod(_get_pydantic_core_schema)
    print("✅ Applied Pydantic bridge for MCP ClientSession")
except ImportError:
    pass


import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# 2. INTERNAL IMPORTS
from sre_agent.tools import (
    fetch_trace,
)

app = FastAPI(title="SRE Agent Toolbox API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. TOOL ENDPOINTS


@app.get("/api/tools/trace/{trace_id}")
async def get_trace(trace_id: str, project_id: str | None = None):
    """Fetch and summarize a trace."""
    try:
        # Note: ToolContext is required by ADK tools
        from google.adk.tools import ToolContext

        # We need a runner to provide context if the tool requires it
        # But fetch_trace might work with a dummy context
        ctx = ToolContext()
        result = await fetch_trace(
            trace_id=trace_id, project_id=project_id, tool_context=ctx
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/tools/logs/analyze")
async def analyze_logs(payload: dict[str, Any]):
    """Fetch logs and extract patterns."""
    try:
        from google.adk.tools import ToolContext

        from sre_agent.tools import extract_log_patterns, list_log_entries

        ctx = ToolContext()
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
from google.adk.cli.adk_web_server import AdkWebServer  # noqa: E402

# Mimic 'adk web sre_agent'
agents_dir = "sre_agent"
adk_web_server = AdkWebServer(agents_dir=agents_dir)
# This creates the FastAPI app with /copilotkit and other routes
adk_app = adk_web_server.get_fast_api_app(
    web_assets_dir=None  # We don't need the internal ADK React UI
)

# Mount the ADK app into our main app
app.mount("/", adk_app)

if __name__ == "__main__":
    # Run on 8000
    print("🚀 Starting SRE Agent + Tools API on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
