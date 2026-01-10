# SRE Agent

## Agent Rules
- **Keep Docs Up To Date**: When you make changes to the codebase, you MUST update `README.md` and `AGENTS.md` to reflect those changes. This is a strict rule.
- **Reference AGENTS.md**: Use this file as the source of truth for developer workflows.

## System Architecture

```mermaid
flowchart TB
    subgraph User["User Interface"]
        CLI["ADK CLI<br/>(adk run/web)"]
    end

    subgraph SRE["SRE Agent (Gemini 2.5 Pro)"]
        Main["sre_agent<br/>(Main Orchestrator)"]
    end

    subgraph TraceSubAgents["Trace Analysis Sub-Agents"]
        direction TB
        Stage0["Stage 0: Aggregate<br/>aggregate_analyzer"]

        subgraph Stage1["Stage 1: Triage (Parallel)"]
            Latency["latency_analyzer"]
            Error["error_analyzer"]
            Structure["structure_analyzer"]
            Stats["statistics_analyzer"]
        end

        subgraph Stage2["Stage 2: Deep Dive (Parallel)"]
            Causality["causality_analyzer"]
            Impact["service_impact_analyzer"]
        end
    end

    subgraph LogSubAgents["Log Analysis Sub-Agents"]
        LogPattern["log_pattern_extractor<br/>(Drain3 Algorithm)"]
    end

    subgraph Tools["Tools"]
        subgraph TraceTools["Trace Tools"]
            TT1["fetch_trace"]
            TT2["list_traces"]
            TT3["compare_span_timings"]
            TT4["find_structural_differences"]
        end

        subgraph BQTools["BigQuery Tools"]
            BQ1["analyze_aggregate_metrics"]
            BQ2["find_exemplar_traces"]
            BQ3["compare_time_periods"]
            BQ4["detect_trend_changes"]
        end

        subgraph LogTools["Log Tools"]
            LT1["extract_log_patterns"]
            LT2["compare_log_patterns"]
            LT3["analyze_log_anomalies"]
            LT4["list_log_entries"]
        end

        subgraph MetricsTools["Metrics Tools"]
            MT1["list_time_series"]
            MT2["mcp_query_range"]
        end
    end

    subgraph GCP["Google Cloud Platform"]
        Trace["Cloud Trace API"]
        Logging["Cloud Logging API"]
        Monitoring["Cloud Monitoring API"]
        BigQuery["BigQuery"]
    end

    CLI --> Main
    Main --> Stage0
    Main --> Stage1
    Main --> Stage2
    Main --> LogPattern

    Stage0 --> BQTools
    Stage1 --> TraceTools
    Stage2 --> TraceTools
    LogPattern --> LogTools

    Main --> TraceTools
    Main --> LogTools
    Main --> MetricsTools
    Main --> BQTools

    TraceTools --> Trace
    LogTools --> Logging
    MetricsTools --> Monitoring
    BQTools --> BigQuery

    classDef gemini fill:#4285f4,stroke:#1a73e8,color:white
    classDef subagent fill:#34a853,stroke:#1e8e3e,color:white
    classDef tool fill:#fbbc04,stroke:#f9ab00,color:black
    classDef gcp fill:#ea4335,stroke:#c5221f,color:white

    class Main gemini
    class Stage0,Latency,Error,Structure,Stats,Causality,Impact,LogPattern subagent
    class TT1,TT2,TT3,TT4,BQ1,BQ2,BQ3,BQ4,LT1,LT2,LT3,LT4,MT1,MT2 tool
    class Trace,Logging,Monitoring,BigQuery gcp
```

## Architecture Overview

The SRE Agent uses a **multi-stage analysis pipeline** with specialized sub-agents:

### Trace Analysis Pipeline

1. **Stage 0 (Aggregate)**: BigQuery-powered analysis using `aggregate_analyzer` sub-agent
   - Tools: `analyze_aggregate_metrics`, `find_exemplar_traces`, `compare_time_periods`, `detect_trend_changes`, `correlate_logs_with_trace`
   - Purpose: Start broad - analyze thousands of traces to identify patterns

2. **Stage 1 (Triage)**: Parallel trace comparison using 4 sub-agents
   - Agents: `latency_analyzer`, `error_analyzer`, `structure_analyzer`, `statistics_analyzer`
   - Purpose: Compare specific traces to identify WHAT is different

3. **Stage 2 (Deep Dive)**: Root cause analysis using 2 sub-agents
   - Agents: `causality_analyzer`, `service_impact_analyzer`
   - Purpose: Determine WHY differences occurred and assess blast radius

### Log Analysis Pipeline

- **log_pattern_extractor**: Uses Drain3 algorithm for log template extraction
  - Tools: `extract_log_patterns`, `compare_log_patterns`, `analyze_log_anomalies`
  - Purpose: Compress repetitive logs into patterns, detect anomalies by comparing time periods

## Data Flow

```mermaid
sequenceDiagram
    participant User
    participant SRE as SRE Agent
    participant BQ as BigQuery
    participant Trace as Cloud Trace
    participant Logs as Cloud Logging
    participant Drain3 as Drain3 Engine

    User->>SRE: "Investigate high latency in checkout-service"

    Note over SRE: Stage 0: Aggregate Analysis
    SRE->>BQ: analyze_aggregate_metrics()
    BQ-->>SRE: Service health metrics
    SRE->>BQ: find_exemplar_traces()
    BQ-->>SRE: baseline_trace_id, outlier_trace_id

    Note over SRE: Stage 1: Triage (Parallel)
    par Latency Analysis
        SRE->>Trace: fetch_trace(baseline)
        SRE->>Trace: fetch_trace(outlier)
        Trace-->>SRE: Span timings
    and Error Analysis
        SRE->>Trace: extract_errors()
        Trace-->>SRE: Error spans
    and Log Pattern Analysis
        SRE->>Logs: list_log_entries(baseline_period)
        SRE->>Logs: list_log_entries(incident_period)
        Logs-->>SRE: Raw log entries
        SRE->>Drain3: extract_log_patterns()
        Drain3-->>SRE: Compressed patterns
        SRE->>Drain3: compare_log_patterns()
        Drain3-->>SRE: NEW/INCREASED patterns
    end

    Note over SRE: Stage 2: Deep Dive
    SRE->>SRE: Synthesize findings

    SRE-->>User: Root cause + recommendations
```

## Dev Environment Tips

- Use `uv sync` to install dependencies and create the virtual environment.
- Use `uv run adk web sre_agent` to launch the agent's web interface (Streamlit-based).
- Use `uv run adk run sre_agent` to launch the interactive terminal interface.
- Environment variables are managed in `.env`. Copy `.env.example` to `.env` and set `GOOGLE_CLOUD_PROJECT`.
- The agent uses widespread `opentelemetry` instrumentation. Logs are visible in the console and Cloud Logging.
- Agent definitions are in `sre_agent/agent.py` and `sub_agents/`.
- `deploy/` contains scripts for deploying to Vertex AI Agent Engine (`uv run python deploy/deploy.py`).

## Testing Instructions

- Run the full test suite with `uv run pytest`.
- Tests are located in the `tests/` directory.
- Use `uv run pytest -s` to see stdout/logging during tests.
- When modifying agents, add new tests to `tests/` to verify behavior.
- Run type checks with `uv run mypy .` (if configured in `optional-dependencies`).

## Code Quality & Linting

- **Flake8**: Used for style enforcement.
  - **Config**: `.flake8`
  - **Max Line Length**: 127
  - **Max Complexity**: 10
  - **Ignored**: E203, E501
  - **Run**: `uv run flake8 .`

## PR Instructions

- Ensure `uv.lock` is updated if dependencies change.
- Verify that `uv run pytest` passes cleanly.
- If modifying prompts (`prompt.py`), verify agent behavior with `uv run adk run sre_agent` using a known trace ID.
- Title format: `[sre-agent] <Description of changes>`
