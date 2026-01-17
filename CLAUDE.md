# CLAUDE.md: AI Development Guide for Auto SRE Agent

**Last Updated**: 2026-01-17
**Purpose**: This guide codifies core logic, architecture patterns, and best practices for AI-assisted development on the Auto SRE Agent codebase.

---

## 🚀 Quick Start for Claude

**ALWAYS start by reading these files first:**
1. **CLAUDE.md** (this file) - Core architecture and patterns
2. **README.md** - High-level architecture and features
3. **AGENTS.md** - Development workflow and code quality rules

**Before ANY code change:**
```bash
# Read the relevant source files first
# Make changes
uv run poe lint      # Must pass clean
uv run poe test      # Must pass with 70%+ coverage
```

---

## 📚 Codebase Architecture

### High-Level Overview

**Pattern**: "Council of Experts" - A main orchestrator delegates to specialized sub-agents.

**Technology Stack**:
- **Language**: Python 3.10+ with strict MyPy type checking
- **Agent Framework**: Google Agent Development Kit (ADK)
- **LLM**: Gemini 2.5 Flash
- **API Strategy**: Hybrid (MCP for heavy-lifting, Direct API for speed)
- **Testing**: pytest + pytest-asyncio + pytest-cov (70% coverage minimum)
- **Linting**: Ruff + MyPy + Codespell + Deptry

### Core Components

```
sre_agent/
├── agent.py              # Main orchestrator with 3-stage analysis pipeline
├── prompt.py             # Agent personality and instructions
├── schema.py             # Pydantic models (all with extra="forbid")
├── sub_agents/           # Specialist agents (trace, logs, metrics, alerts)
├── tools/                # Tool implementations
│   ├── mcp/              # Model Context Protocol (heavy SQL/queries)
│   ├── clients/          # Direct GCP API clients (low-latency)
│   ├── analysis/         # Pure analysis functions
│   └── common/           # Shared utilities (decorators, cache, telemetry)
├── services/             # Infrastructure (session management, storage)
└── server.py             # FastAPI server
```

---

## 🎯 Core Patterns You MUST Follow

### 1. Pydantic Schema Pattern

**ALL Pydantic models MUST use:**
```python
from pydantic import BaseModel, ConfigDict

class MySchema(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    field: str
```

**Why**: `extra="forbid"` catches LLM hallucinations (extra fields) immediately.

### 2. Tool Decorator Pattern

**ALL tools MUST use `@adk_tool` decorator:**
```python
from sre_agent.tools.common.decorators import adk_tool

@adk_tool
async def my_tool(arg: str) -> str:
    """Tool description."""
    # Implementation
    return result
```

**Benefits**: Automatic OpenTelemetry spans, metrics, logging, error handling.

### 3. Error Response Pattern

**ALL tools MUST follow `BaseToolResponse` structure:**
```python
{
    "status": "success" | "error" | "partial",
    "result": {...},  # Only if successful
    "error": "error message",  # Only if failed
    "metadata": {...}  # Optional context
}
```

**For non-retryable errors, explicitly state:**
```python
return json.dumps({
    "status": "error",
    "error": "MCP session timeout. DO NOT retry. Use Direct API instead.",
    "non_retryable": True
})
```

### 4. Client Singleton Pattern

**ALL GCP clients MUST use factory pattern:**
```python
from sre_agent.tools.clients.factory import get_trace_client

def my_function():
    client = get_trace_client()  # Thread-safe singleton
    # Use client
```

### 5. Caching Pattern

**Use data cache for expensive operations:**
```python
from sre_agent.tools.common.cache import get_data_cache

cache = get_data_cache()
cache_key = f"trace:{trace_id}"

# Check cache
cached = cache.get(cache_key)
if cached:
    return cached

# Fetch and cache
result = await fetch_data()
cache.put(cache_key, result)
return result
```

**TTL**: 300 seconds (5 minutes)

### 6. MCP vs Direct API Strategy

**Use MCP (`mcp/`) for**:
- BigQuery SQL execution (fleet-wide analysis)
- Complex log queries with aggregation
- Heavy PromQL queries

**Use Direct API (`clients/`) for**:
- Single trace fetching (low-latency)
- Simple log queries
- Real-time metric queries
- Alert policy queries

**Fallback Rule**: If MCP fails, tools MUST fall back to Direct API and document this in error messages.

---

## 🛠️ Development Workflow

### Before ANY Code Change

1. **Read relevant files**:
   ```bash
   # Read the file you're modifying
   # Read related test files
   # Read related schema files
   ```

2. **Understand the context**:
   - What sub-agent uses this tool?
   - What other tools does it interact with?
   - What are the error cases?

### Making Changes

1. **Add/Modify Code**
2. **Run linter** (catches 90% of issues):
   ```bash
   uv run poe lint
   ```
3. **Run tests**:
   ```bash
   uv run poe test
   ```
4. **Fix any failures** and repeat steps 2-3

### Adding a New Tool

**Checklist**:
1. ✅ Create function in `/sre_agent/tools/` (appropriate subdirectory)
2. ✅ Add `@adk_tool` decorator
3. ✅ Add docstring with clear description
4. ✅ Add to `__all__` in `/sre_agent/tools/__init__.py`
5. ✅ Add to `base_tools` list in `/sre_agent/agent.py`
6. ✅ Add to `TOOL_NAME_MAP` in `/sre_agent/agent.py`
7. ✅ Add `ToolConfig` entry in `/sre_agent/tools/config.py`
8. ✅ Add test in `tests/sre_agent/tools/`
9. ✅ Run `uv run poe lint` and `uv run poe test`
10. ✅ Update README.md tool table (if user-facing)

**Example**:
```python
# File: sre_agent/tools/clients/trace.py

@adk_tool
async def fetch_trace(project_id: str, trace_id: str) -> str:
    """Fetch a single trace by ID from Cloud Trace API.

    Args:
        project_id: GCP project ID
        trace_id: Trace ID (128-bit hex string)

    Returns:
        JSON string with trace data or error response
    """
    try:
        client = get_trace_client()
        # Implementation
        return json.dumps({"status": "success", "result": trace_data})
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})
```

### Adding a New Sub-Agent

**Checklist**:
1. ✅ Create file in `/sre_agent/sub_agents/<name>.py`
2. ✅ Define clear prompt with:
   - Persona (e.g., "Latency Specialist")
   - Workflow steps
   - Tool usage guidelines
   - Output format
3. ✅ Select curated tool subset (only what's needed)
4. ✅ Export in `/sre_agent/sub_agents/__init__.py`
5. ✅ Add to `sub_agents` list in `/sre_agent/agent.py`
6. ✅ Add test in `tests/sre_agent/sub_agents/`
7. ✅ Run `uv run poe lint` and `uv run poe test`
8. ✅ Update README.md architecture diagram

**Example Structure**:
```python
# File: sre_agent/sub_agents/latency.py

from google.ai.generativelanguage import LlmAgent

LATENCY_ANALYZER_PROMPT = """
You are a Latency Specialist. Your role is to...

**Workflow**:
1. Fetch trace data
2. Calculate span durations
3. Identify critical path
4. Report bottlenecks

**Output Format**:
{
    "bottlenecks": [...],
    "critical_path": [...],
    "recommendations": [...]
}
"""

latency_analyzer = LlmAgent(
    model="gemini-2.5-flash",
    system_instruction=LATENCY_ANALYZER_PROMPT,
    tools=[
        # Only latency-relevant tools
        "fetch_trace",
        "calculate_span_durations",
        "analyze_critical_path",
    ]
)
```

---

## 🧪 Testing Requirements

### Coverage Requirement

**Minimum**: 70% test coverage (enforced in CI)

### Test Structure

```
tests/
├── sre_agent/
│   ├── e2e/                    # End-to-end tests
│   ├── sub_agents/             # Sub-agent tests
│   └── tools/                  # Tool tests
│       ├── clients/            # API client tests
│       ├── analysis/           # Analysis logic tests
│       └── mcp/                # MCP integration tests
```

### Writing Tests

**Pattern**: Mirror source structure
- `sre_agent/tools/clients/trace.py` → `tests/sre_agent/tools/clients/test_trace.py`

**Mock External APIs**:
```python
from unittest.mock import patch, MagicMock

@patch("sre_agent.tools.clients.factory.get_trace_client")
async def test_fetch_trace(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Setup mock response
    mock_client.get_trace.return_value = {...}

    # Test
    result = await fetch_trace("project-id", "trace-id")
    assert "success" in result
```

**MCP Testing**:
Set environment variable to use mock:
```python
import os
os.environ["USE_MOCK_MCP"] = "true"
```

### Running Tests

```bash
# All tests
uv run poe test

# Specific test file
uv run pytest tests/sre_agent/tools/clients/test_trace.py

# Specific test function
uv run pytest tests/sre_agent/tools/clients/test_trace.py::test_fetch_trace

# With coverage report
uv run pytest --cov=sre_agent --cov-report=html
```

---

## 🎨 Code Style & Type Checking

### Type Annotations (Strict MyPy)

**ALL functions MUST have explicit types:**

```python
# ✅ GOOD
def process_trace(trace_id: str, project: str | None = None) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    total: float = 0.0
    return {"items": items, "total": total}

# ❌ BAD
def process_trace(trace_id, project=None):  # Missing types
    items = []  # Implicit Any
    total = 0  # Should be 0.0 for float
    return {"items": items, "total": total}
```

**Key Rules**:
- Optional types: `str | None` (NOT `str = None` without type)
- Empty containers: `items: list[dict[str, Any]] = []`
- Float initialization: `val: float = 0.0` (not `0`)
- No implicit `Any`

### Import Style

```python
# Absolute imports for cross-module
from sre_agent.tools.clients.trace import fetch_trace
from sre_agent.schema import BaseToolResponse

# Relative imports for siblings/parents
from .trace import fetch_trace
from ..common.decorators import adk_tool

# Type checking imports (avoid circular deps)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sre_agent.agent import SREAgent
```

### Linting Stack

**Run before every commit:**
```bash
uv run poe lint
```

**Components**:
- **Ruff**: Formatting, import sorting, linting (replaces Black/Flake8/Isort)
- **MyPy**: Strict type checking
- **Codespell**: Spelling checker
- **Deptry**: Dependency checker (unused/missing in pyproject.toml)
- **detect-secrets**: Secret scanning

---

## 🔍 Common Tasks

### Task 1: Fix a Bug in a Tool

1. **Read the tool file**:
   ```bash
   # Example: Bug in fetch_trace
   cat sre_agent/tools/clients/trace.py
   ```

2. **Read the test file**:
   ```bash
   cat tests/sre_agent/tools/clients/test_trace.py
   ```

3. **Reproduce the issue**:
   ```bash
   uv run pytest tests/sre_agent/tools/clients/test_trace.py -v
   ```

4. **Fix the code**

5. **Run linter and tests**:
   ```bash
   uv run poe lint
   uv run poe test
   ```

### Task 2: Add a New Analysis Feature

1. **Create analysis function** in `sre_agent/tools/analysis/`
2. **Add tests** in `tests/sre_agent/tools/analysis/`
3. **Create tool wrapper** (if needed) that uses the analysis function
4. **Add to agent** following "Adding a New Tool" checklist
5. **Run linter and tests**

### Task 3: Improve Error Handling

**Pattern**:
```python
@adk_tool
async def my_tool(arg: str) -> str:
    try:
        # Implementation
        return json.dumps({
            "status": "success",
            "result": result
        })
    except SpecificError as e:
        # Log with context
        logger.error(f"Specific error in my_tool: {e}", exc_info=True)
        return json.dumps({
            "status": "error",
            "error": f"Specific error: {str(e)}",
            "non_retryable": True  # If shouldn't retry
        })
    except Exception as e:
        # Catch-all
        logger.error(f"Unexpected error in my_tool: {e}", exc_info=True)
        return json.dumps({
            "status": "error",
            "error": f"Unexpected error: {str(e)}"
        })
```

### Task 4: Optimize Performance

**Strategies**:
1. **Add caching** for repeated data fetches
2. **Use batch APIs** instead of loops
3. **Parallelize independent operations** with `asyncio.gather()`
4. **Reduce LLM context** by summarizing data before sending
5. **Profile slow operations**:
   ```python
   import time
   start = time.time()
   result = await slow_operation()
   logger.info(f"slow_operation took {time.time() - start:.2f}s")
   ```

### Task 5: Debug MCP Issues

**Common Issues**:
1. **Session timeout**: Fall back to Direct API
2. **Missing credentials**: Check `GOOGLE_CLOUD_PROJECT` env var
3. **Schema errors**: Check BigQuery table schema matches expectations

**Debug Steps**:
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run specific test
uv run pytest tests/sre_agent/tools/mcp/test_gcp.py -v -s

# Check MCP mock is used in tests
export USE_MOCK_MCP=true
```

---

## 🚨 Common Pitfalls & Solutions

### Pitfall 1: Missing Tool Registration

**Symptom**: Tool exists but agent can't find it.

**Solution**: Check ALL registration points:
- `__all__` in `/sre_agent/tools/__init__.py`
- `base_tools` in `/sre_agent/agent.py`
- `TOOL_NAME_MAP` in `/sre_agent/agent.py`
- `ToolConfig` in `/sre_agent/tools/config.py`

### Pitfall 2: Import Errors

**Symptom**: `ImportError` or `ModuleNotFoundError`

**Solution**:
```bash
# Sync dependencies
uv run poe sync

# Check if module is installed
uv pip list | grep <module-name>

# Verify import path
python -c "from sre_agent.tools import fetch_trace; print('OK')"
```

### Pitfall 3: Type Checking Errors

**Symptom**: MyPy errors like "Missing type annotation"

**Solution**: Add explicit types:
```python
# ❌ Before
def process(data):
    items = []
    return items

# ✅ After
def process(data: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    return items
```

### Pitfall 4: Test Coverage Drops

**Symptom**: CI fails with "Coverage dropped below 80%"

**Solution**:
```bash
# Check coverage report
uv run pytest --cov=sre_agent --cov-report=html

# Open htmlcov/index.html to see uncovered lines

# Add tests for uncovered code
```

### Pitfall 5: Pydantic Validation Errors

**Symptom**: `ValidationError: Extra inputs are not permitted`

**Solution**: Check schema has `extra="forbid"`:
```python
class MySchema(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    # Fields...
```

### Pitfall 6: Async/Await Issues

**Symptom**: `RuntimeWarning: coroutine was never awaited`

**Solution**: Always `await` async functions:
```python
# ❌ Wrong
result = fetch_trace(project, trace_id)

# ✅ Correct
result = await fetch_trace(project, trace_id)
```

---

## 🌟 Best Practices for AI-Assisted Development

### 1. Always Read Before Modifying

**Never propose changes to code you haven't read.**
```bash
# Read the file first
cat sre_agent/tools/clients/trace.py

# Then make changes
```

### 2. Understand the Full Context

Before making a change, understand:
- What sub-agents use this tool?
- What are the dependencies?
- What are the edge cases?
- What tests exist?

### 3. Make Minimal Changes

**Avoid over-engineering:**
- Only make changes that are directly requested
- Don't add "improvements" beyond the scope
- Don't refactor surrounding code
- Don't add docstrings to code you didn't change

### 4. Follow the Existing Patterns

**Don't reinvent patterns:**
- Use `@adk_tool` decorator (don't create your own)
- Use `get_trace_client()` factory (don't instantiate directly)
- Use `BaseToolResponse` structure (don't create custom)
- Use existing error handling patterns

### 5. Test-Driven Development

**Write tests first when possible:**
```python
# 1. Write failing test
def test_new_feature():
    result = await new_feature("input")
    assert result == "expected"

# 2. Run test (should fail)
# 3. Implement feature
# 4. Run test (should pass)
```

### 6. Incremental Changes

**Make small, verifiable changes:**
1. Change one file
2. Run linter
3. Run tests
4. Commit
5. Repeat

### 7. Document Intent, Not Implementation

**Good comments explain WHY, not WHAT:**
```python
# ❌ Bad comment (explains what)
# Loop through traces
for trace in traces:
    process(trace)

# ✅ Good comment (explains why)
# Process traces in sequence to avoid rate limiting
for trace in traces:
    process(trace)
```

### 8. Use Type Hints as Documentation

**Types are self-documenting:**
```python
# ✅ Clear from types
def fetch_traces(
    project_id: str,
    start_time: datetime,
    limit: int = 100
) -> list[dict[str, Any]]:
    ...
```

### 9. Handle Errors Gracefully

**Always provide actionable error messages:**
```python
# ❌ Bad error
raise Exception("Failed")

# ✅ Good error
raise ValueError(
    f"Invalid trace_id format: {trace_id}. "
    "Expected 128-bit hex string (32 characters)."
)
```

### 10. Keep the User Informed

**For long-running operations, add progress logging:**
```python
logger.info(f"Fetching {len(trace_ids)} traces...")
for i, trace_id in enumerate(trace_ids):
    if i % 10 == 0:
        logger.info(f"Progress: {i}/{len(trace_ids)} traces fetched")
    await fetch_trace(project, trace_id)
logger.info("All traces fetched successfully")
```

---

## 🔐 Security & Secrets

### Never Commit Secrets

**Scan before commit:**
```bash
uv run detect-secrets scan --baseline .secrets.baseline
```

**If false positive:**
```bash
uv run detect-secrets scan --baseline .secrets.baseline --update
```

### Environment Variables

**Required**:
- `GOOGLE_CLOUD_PROJECT`: GCP project ID
- `GOOGLE_CLOUD_LOCATION`: GCP region (default: us-central1)

**Optional**:
- `TRACE_PROJECT_ID`: Override trace project
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `USE_MOCK_MCP`: Use mock MCP in tests

**Never hardcode**:
- API keys
- Project IDs (use env vars)
- Service account credentials

---

## 📊 Monitoring & Observability

### OpenTelemetry Instrumentation

**Every tool call generates**:
- **Span**: With attributes (tool name, arguments, duration)
- **Metrics**: Execution count, latency
- **Logs**: Entry, completion, errors

**Configured in**: `/sre_agent/tools/common/telemetry.py`

### Logging Best Practices

```python
import logging
logger = logging.getLogger(__name__)

# Use appropriate levels
logger.debug("Detailed debug info")
logger.info("Important state changes")
logger.warning("Recoverable issues")
logger.error("Errors requiring attention", exc_info=True)

# Include context
logger.info(f"Fetching trace {trace_id} from project {project_id}")
```

---

## 🚀 Deployment

### Local Development

```bash
# Backend only
uv run poe web

# Full stack (backend + frontend)
uv run poe dev

# Interactive terminal
uv run poe run
```

### Deployment to Agent Engine

```bash
# Backend to Vertex AI Agent Engine
uv run poe deploy

# Frontend to Cloud Run
uv run poe deploy-web

# Full stack to Cloud Run
uv run poe deploy-all
```

**See**: `deploy/README.md` for detailed deployment guide.

---

## 🆘 Troubleshooting

### Issue: Tests Failing

**Debug Steps**:
```bash
# Run specific test with verbose output
uv run pytest tests/path/to/test.py::test_name -v -s

# Check test logs
uv run pytest --log-cli-level=DEBUG

# Use debugger
uv run pytest --pdb
```

### Issue: Linter Failing

**Common Fixes**:
```bash
# Auto-fix formatting issues
uv run ruff check --fix sre_agent/

# Auto-fix import sorting
uv run ruff check --select I --fix sre_agent/

# Check MyPy specific file
uv run mypy sre_agent/tools/clients/trace.py
```

### Issue: Import Errors in Production

**Check**:
1. All dependencies in `pyproject.toml`
2. Correct import paths (absolute vs relative)
3. `__init__.py` files in all package directories

### Issue: MCP Timeout

**Solution**: Use Direct API fallback:
```python
try:
    result = await mcp_list_log_entries(...)
except TimeoutError:
    logger.warning("MCP timeout, using Direct API")
    result = await list_log_entries(...)
```

---

## 📚 Additional Resources

### Key Files to Reference

- **Architecture**: `README.md` (Mermaid diagrams)
- **Development Workflow**: `AGENTS.md` (code quality, git standards)
- **Tool Reference**: `sre_agent/tools/__init__.py` (all available tools)
- **Sub-Agent Reference**: `sre_agent/sub_agents/__init__.py` (all specialists)
- **Schema Reference**: `sre_agent/schema.py` (all data models)

### Command Reference

```bash
# Dependencies
uv run poe sync              # Install/update dependencies

# Development
uv run poe run               # Interactive terminal agent
uv run poe web               # Backend server only
uv run poe dev               # Full stack (backend + frontend)

# Quality Checks
uv run poe lint              # Run all linters
uv run poe pre-commit        # Run pre-commit hooks
uv run poe test              # Run tests with coverage

# Deployment
uv run poe deploy            # Deploy backend to Agent Engine
uv run poe deploy-web        # Deploy frontend to Cloud Run
uv run poe deploy-all        # Deploy full stack to Cloud Run

# Utilities
uv run poe list              # List deployed agents
uv run poe delete --resource_id ID  # Delete agent
```

### External Documentation

- **Google ADK**: https://github.com/googleapis/python-genai
- **MCP**: https://modelcontextprotocol.io/
- **OpenTelemetry**: https://opentelemetry.io/docs/languages/python/
- **Pydantic**: https://docs.pydantic.dev/
- **pytest**: https://docs.pytest.org/

---

## 🎓 Learning Path for New Contributors

1. **Week 1**: Read `README.md`, `AGENTS.md`, `CLAUDE.md`
2. **Week 2**: Explore `/sre_agent/agent.py`, `/sre_agent/prompt.py`
3. **Week 3**: Study sub-agents in `/sre_agent/sub_agents/`
4. **Week 4**: Deep dive into tools in `/sre_agent/tools/`
5. **Week 5**: Write your first tool or sub-agent
6. **Week 6**: Contribute to tests and documentation

---

## ✅ Pre-Commit Checklist

Before committing code, verify:

- [ ] Read all files I'm modifying
- [ ] Understood the context and dependencies
- [ ] Made minimal, focused changes
- [ ] Added/updated tests for changes
- [ ] Ran `uv run poe lint` (passed clean)
- [ ] Ran `uv run poe test` (passed with 70%+ coverage)
- [ ] Updated docstrings if adding new functions
- [ ] Updated README.md if adding user-facing features
- [ ] Used conventional commit message format
- [ ] No secrets or credentials committed

---

## 🎯 Summary: Golden Rules

1. **Always read before modifying** - Never propose changes to unread code
2. **Follow existing patterns** - Don't reinvent the wheel
3. **Test everything** - 70% coverage minimum, no exceptions
4. **Type everything** - Strict MyPy, explicit types always
5. **Lint before commit** - `uv run poe lint` must pass
6. **Make minimal changes** - Avoid over-engineering
7. **Document intent** - Comments explain WHY, not WHAT
8. **Handle errors gracefully** - Provide actionable error messages
9. **Use the tools** - `@adk_tool`, factories, caching, etc.
10. **Keep learning** - Read the codebase, ask questions, improve

---

**Happy Coding! 🚀**
