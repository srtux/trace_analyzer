# SRE Agent Test Suite

This directory contains the test suite for the SRE Agent (GCP Observability Analysis Toolkit). The tests have been refactored to mirror the source code structure, ensuring better organization and maintainability.

## 📂 Directory Structure

```text
tests/
├── conftest.py                   # Global fixtures (Mocks, Sample Logs, Synthetic Traces)
├── data/                         # Static JSON data files for trace analysis tests
├── fixtures/                     # Dynamic synthetic data generators
│   └── synthetic_otel_data.py    # OTel trace data generation utilities
└── sre_agent/                    # Main test package (Mirrors source code)
    ├── e2e/                      # End-to-End and Integration tests
    │   ├── test_agent_execution.py    # Orchestration tests
    │   ├── test_agent_integration.py  # Root agent initialization
    │   ├── test_analysis_e2e.py       # E2E analysis workflows
    │   ├── test_mocks_e2e.py          # E2E tests with full system mocks
    │   └── test_trace_selection.py    # E2E trace selection logic
    ├── sub_agents/               # Tests for specialized analysts
    │   ├── test_log_pattern_extractor.py
    │   └── test_metrics.py            # Metrics analyzer tests
    ├── tools/                    # Unit tests for core tools
    │   ├── analysis/             # Analysis logic subdirectories
    │   │   ├── bigquery/         # BigQuery SQL tool tests
    │   │   ├── logs/             # Log pattern analysis tests
    │   │   ├── metrics/          # Metrics statistical tests
    │   │   └── trace/            # Trace comparison & statistical tests
    │   ├── clients/              # Direct API client tests
    │   ├── common/               # Shared utilities (caching, decorators)
    │   └── logs/                 # Log extraction utility tests
    ├── test_agent_project_id.py  # Config verification
    ├── test_e2e_cujs.py          # End-to-end Critical User Journeys
    ├── test_mcp_integration.py   # MCP session & toolset tests
    ├── test_orchestration.py     # Agent orchestration logic
    └── test_schema.py            # Pydantic model validation
```

## 🧪 Test Categories

### 1. End-to-End Tests (`sre_agent/e2e/`)
These tests verify the integrated behavior of the system, including the "Council of Experts" orchestration and agent lifecycle.
*   **`test_agent_execution.py`**: Validates the full analysis workflow.
*   **`test_agent_integration.py`**: Smoke tests for agent initialization and tool registration.

### 2. Unit Tests
*   **Analysis Logic** (`tools/analysis/`): Tests for statistical analysis, comparison logic, and log pattern extraction. Organized by signal type (Trace, Logs, Metrics, BigQuery).
*   **Clients** (`tools/clients/`): Tests for API interaction, ensuring mocks are used correctly to avoid real network calls.
*   **Infrastructure** (`tools/common/`, `test_schema.py`): Tests for schemas, telemetry, and caching.

## 🛠️ Global Fixtures (`conftest.py`)

The `conftest.py` file provides shared resources available to all tests:
*   **Synthetic Traces/Logs**: Helpers to generate random trace IDs, span IDs, and timestamps.
*   **Sample Data**: Pre-defined log entry payloads (Text, JSON, Proto).
*   **Mock Clients**: Shared mock objects for Cloud Logging, Trace, and BigQuery APIs.

## 🚀 Running the Tests

To run the full test suite (81% Coverage):

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=sre_agent --cov-report=term-missing

# Run specific E2E tests
uv run pytest tests/sre_agent/e2e/test_agent_execution.py
```

## 📝 Best Practices
*   **Mocks vs. Real APIs**: Use the mocks provided in `conftest.py` to avoid making actual GCP calls during unit tests.
*   **Data Generation**: Use the utilities in `tests/fixtures/synthetic_otel_data.py` for complex trace structures rather than hardcoding large dicts.
*   **Naming**: Prefix test files with `test_` and test functions with `test_` for automatic discovery by `pytest`.
