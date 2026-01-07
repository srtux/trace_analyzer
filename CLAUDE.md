# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Google Agent Development Kit (ADK) based agent that performs deep diff analysis on distributed traces from Google Cloud Trace. It uses a hierarchical orchestration pattern with a root agent coordinating 5 specialized sub-agents (Latency, Error, Structure, Statistics, Causality) that run in parallel to analyze traces.

## Development Commands

### Environment Setup
```bash
# Install dependencies using uv (high-performance dependency manager)
uv sync

# Configure environment
cp .env.example .env
# Edit .env to set GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION
```

### Running the Agent
```bash
# Launch interactive terminal UI
uv run adk run .

# Launch web-based interface
uv run adk web
```

### Testing
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_agent_integration.py

# Run tests with verbose output
uv run pytest -v

# Run async tests (uses pytest-asyncio)
uv run pytest -v --asyncio-mode=auto
```

### Code Quality
```bash
# Run linting with ruff
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .

# Run type checking with mypy
uv run mypy trace_analyzer
```

## Architecture Overview

### Agent Hierarchy

The agent uses a **hierarchical orchestration pattern**:

1. **Root Agent** (`trace_analyzer/agent.py`):
   - Orchestrates trace discovery and high-level analysis
   - Manages tool execution flow
   - Synthesizes results from specialist agents

2. **Parallel Analysis Squad** (`ParallelAgent`):
   - Executes 5 specialist agents concurrently
   - Each specialist focuses on one aspect of trace comparison
   - Located in `trace_analyzer/sub_agents/`

### Sub-Agents

All sub-agents follow the same structure: `{name}/agent.py` and `{name}/prompt.py`

- **latency_analyzer**: Identifies span duration differences and performance regressions
- **error_analyzer**: Detects new errors and failure pattern changes
- **structure_analyzer**: Examines call graph topology changes
- **statistics_analyzer**: Performs P50/P90/P95/P99 analysis, z-score anomaly detection, critical path identification
- **causality_analyzer**: Identifies root causes via causal chain analysis

### MCP Integration Pattern

The project uses **lazy MCP (Model Context Protocol) initialization** to avoid aiohttp session conflicts in ASGI/uvicorn environments:

- `LazyMcpRegistryToolset` in `agent.py` defers ApiRegistry initialization until the event loop is running
- This pattern is critical for deployment stability - do not initialize MCP tools at module import time
- BigQuery MCP tools are loaded via `ApiRegistry` with server name pattern: `projects/{project}/locations/global/mcpServers/google-bigquery.googleapis.com-mcp`

### Tools Organization

Located in `trace_analyzer/tools/`:

- **trace_client.py**: Core Cloud Trace API interactions
  - `fetch_trace()`: Get specific trace by ID
  - `list_traces()`: Query traces with advanced filters
  - `find_example_traces()`: Auto-discover baseline (P50) vs anomaly (P95) traces
  - `get_trace_by_url()`: Parse Cloud Console URLs to extract trace IDs

- **trace_filter.py**: `TraceQueryBuilder` for constructing Cloud Trace filter strings
  - Supports span names, latency ranges, attributes, service names, HTTP status/methods
  - Uses Cloud Trace filter syntax (see: https://docs.cloud.google.com/trace/docs/trace-filters)

- **trace_analysis.py**: Core analysis logic and trace summarization

- **statistical_analysis.py**: Statistical and causal analysis algorithms

### Structured Outputs

`trace_analyzer/schema.py` defines Pydantic schemas for structured agent outputs:
- `TraceComparisonReport`: Top-level analysis report
- `LatencyDiff`, `ErrorDiff`, `StructureDiff`: Specific finding types
- `TraceSummary`, `SpanInfo`: Trace metadata

### Telemetry

The project includes comprehensive OpenTelemetry instrumentation (`telemetry.py`):
- All tools record execution duration, count, and success metrics
- Traces are created for each tool execution
- Structured logging via `log_tool_call()`

## Key Technical Constraints

### Python Version
Requires Python 3.10-3.12 (not 3.13+) due to google-cloud-aiplatform compatibility.

### Environment Variables
Required:
- `GOOGLE_CLOUD_PROJECT`: GCP project ID for Cloud Trace and BigQuery access
- `GOOGLE_CLOUD_LOCATION`: GCP region (typically `us-central1`)
- `GOOGLE_GENAI_USE_VERTEXAI=1`: Use Vertex AI for agent engine

Optional:
- `TRACE_PROJECT_ID`: Override project for trace queries (defaults to GOOGLE_CLOUD_PROJECT)

### IAM Permissions
The authenticated user/service account needs:
- `roles/cloudtrace.user`
- `roles/bigquery.dataViewer`
- `roles/bigquery.jobUser`

## Adding New Sub-Agents

To add a new specialist agent:

1. Create directory: `trace_analyzer/sub_agents/{name}/`
2. Create `agent.py` with an `LlmAgent` instance
3. Create `prompt.py` with specialized instructions
4. Add imports to `sub_agents/__init__.py`
5. Add to `trace_analysis_squad.sub_agents` list in `agent.py`

Sub-agents receive trace data via their analysis request and return findings that the root agent synthesizes.

## Testing Strategy

- **Integration tests**: `tests/test_agent_integration.py` validates agent initialization and tool mocking
- **Tool tests**: Mock the Cloud Trace API client (`trace_v1.TraceServiceClient`)
- Use `pytest-asyncio` for async test functions
- Use `pytest.fixture` with `patch.dict(os.environ, ...)` for environment mocking

## Common Patterns

### Tool Call Pattern
All tools in `trace_client.py` follow this pattern:
```python
with tracer.start_as_current_span("tool_name") as span:
    log_tool_call(logger, "tool_name", param1=value1, ...)
    try:
        # Implementation
        return json.dumps(result)
    except Exception as e:
        span.record_exception(e)
        return json.dumps({"error": str(e)})
    finally:
        _record_telemetry("tool_name", success, duration_ms)
```

### Trace Timestamps
Google Cloud Trace API (via proto-plus) returns datetime objects for `start_time`/`end_time`, not Timestamp protos. Use `.timestamp()` to convert to Unix seconds and `.isoformat()` for ISO strings.

## Deployment

See `deploy/deploy.py` for deployment utilities. The lazy MCP initialization pattern is specifically designed to work with uvicorn/ASGI forking modes.
