# SRE Agent Test Suite

This directory contains the test suite for the SRE Agent (GCP Observability Analysis Toolkit). The tests are organized to reflect the architecture of the agent, covering everything from individual tool logic to complex multi-agent orchestration.

## 📂 Directory Structure

```text
tests/
├── conftest.py                # Global fixtures (Mocks, Sample Logs, Synthetic Traces)
├── data/                      # Static JSON data files for trace analysis tests
├── fixtures/                  # Dynamic synthetic data generators
│   └── synthetic_otel_data.py # OTel trace data generation utilities
├── gcp_observability/         # Package-specific unit and integration tests
│   ├── sub_agents/            # Tests for specialized specialists (Latency, Error, etc.)
│   ├── tools/                 # Unit tests for core tools
│   │   ├── clients/           # Tests for API clients (Logging, Monitoring, Trace)
│   │   ├── mcp/               # Tests for MCP tools
│   │   └── analysis/          # Tests for analysis logic
│   ├── test_agent_project_id.py # Config and Project ID fallback verification
│   ├── test_e2e_cujs.py       # Critical User Journey (CUJ) tests
│   └── test_mcp_integration.py # Model Context Protocol session tests
├── test_agent_execution.py    # Orchestration tests for Stage 1 & 2 analysis flows
├── test_agent_integration.py  # Root agent initialization and tool registration
├── test_end_to_end_analysis.py # Trace comparison tests using static data
├── test_trace_selection.py     # Logic for filtering and selecting exemplar traces
└── test_two_stage_agent.py    # Multi-stage agent interaction verification
```

## 🧪 Test Categories

### 1. Root Agent & Orchestration (Top-level)
These tests are located at the top level of the `tests/` directory because they represent the **entry points** and **integrated behavior** of the system.
*   **`test_agent_integration.py`**: Ensures the `root_agent` (from `gcp_observability.agent`) is correctly initialized with its full toolset and sub-agents. This is the "smoke test" for the entire application.
*   **`test_agent_execution.py`**: Validates the **"Council of Experts"** orchestration. It mocks the sub-agents and verifies that the root agent correctly delegates tasks to the Triage and Deep Dive squads.

### 2. Specialized Specialist Tests (`gcp_observability/sub_agents/`)
Tests for the individual sub-agents that perform specific analysis tasks:
*   **Latency Specialist**: Timing comparison and bottleneck detection.
*   **Error Forensics**: Exception tracking and failure comparison.
*   **Structure Mapper**: Call graph topology differences.
*   **Log Whisperer**: Drain3-powered log pattern extraction.

### 3. Tool Utility Tests (`gcp_observability/tools/`)
Unit tests for the atomic capabilities of the agent. These are now organized into:
*   **`clients/`**: Tests for direct API interaction (e.g., `list_log_entries`, `query_promql`).
*   **`analysis/`**: Tests for pure analysis logic (e.g., trace filters, log patterns).
*   **`mcp/`**: Usage tests for MCP toolsets.

## 🛠️ Global Fixtures (`conftest.py`)

The `conftest.py` file provides shared resources available to all tests:
*   **Synthetic Traces/Logs**: Helpers to generate random trace IDs, span IDs, and timestamps.
*   **Sample Data**: Pre-defined log entry payloads (Text, JSON, Proto) and healthy/incident baseline periods.
*   **Mock Clients**: Shared mock objects for Cloud Logging, Trace, and BigQuery APIs.

## 🚀 Running the Tests

To run the full test suite, use `uv run pytest`:

```bash
# Run all tests
uv run pytest

# Run only orchestration tests
uv run pytest tests/test_agent_execution.py

# Run with verbose output and coverage
uv run pytest -v
```

## 📝 Best Practices
*   **Mocks vs. Real APIs**: Use the mocks provided in `conftest.py` to avoid making actual GCP calls during unit tests.
*   **Data Generation**: Use the utilities in `tests/fixtures/synthetic_otel_data.py` for complex trace structures rather than hardcoding large dicts.
*   **Naming**: Prefix test files with `test_` and test functions with `test_` for automatic discovery by `pytest`.
