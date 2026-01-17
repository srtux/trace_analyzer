# SRE Agent Backend

This directory contains the Python backend for the Auto SRE Agent, built using the Google Agent Development Kit (ADK).

## Package Structure

- **`agent.py`**: The main entry point. Defines the system instructions, orchestrator, and initializes the "Council of Experts".
- **`sub_agents/`**: specialized agents (Trace Analysis, Log Analysis, etc.) that perform the actual work.
- **`tools/`**: The tool implementations (BigQuery, Cloud Trace API, etc.) used by the agents.
- **`services/`**: Infrastructure services for session management and storage.
- **`schema.py`**: Pydantic models for structured output.
- **`prompt.py`**: The main system prompt for the orchestrator.

## Key Components

### 1. Orchestrator (`agent.py`)
The `sre_agent` is an `LlmAgent` using `gemini-2.5-flash`. It acts as the manager, deciding which sub-agent or tool to call based on the user's request.

### 2. Council of Experts (`sub_agents/`)
A collection of specialized agents involving:
- **Trace Analysis Squad**: `latency_analyzer`, `error_analyzer`, `structure_analyzer`, `statistics_analyzer`, `resiliency_architect`.
- **Log Analysis**: `log_analyst`.
- **Metrics Analysis**: `metrics_analyzer`.
- **Deep Dive**: `causality_analyzer`, `service_impact_analyzer`, `change_detective`.

### 3. Services (`services/`)
- **Session Management** (`session.py`): Handles conversation history using ADK's `SessionService`. Supports `DatabaseSessionService` (SQLite) for local dev and `VertexAiSessionService` for production.
- **Storage** (`storage.py`): Manages user preferences.

## Development

The backend is a FastAPI application (via ADK).

### Running Locally
```bash
uv run poe web
```

### Tests
```bash
uv run poe test
```
