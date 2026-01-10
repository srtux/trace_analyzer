# SRE Agent

[![Status](https://img.shields.io/badge/Status-Active-success)]()
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)]()
[![Framework](https://img.shields.io/badge/Framework-Google%20ADK-red)]()

An ADK-based agent for analyzing telemetry data from Google Cloud Observability: **traces**, **logs**, and **metrics**. Specializes in distributed trace analysis with multi-stage investigation capabilities.

## Architecture

The agent is built using the Google Agent Development Kit (ADK). It uses a **"Council of Experts"** orchestration pattern where the main **SRE Agent** coordinates specialized analysis through high-level orchestration tools.

### System Architecture

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'fontFamily': 'arial',
    'fontSize': '16px',
    'lineColor': '#333333',
    'primaryTextColor': '#000000',
    'tertiaryColor': '#ffffff',
    'clusterBkg': '#fafafa',
    'clusterBorder': '#999999'
  }
}}%%
flowchart TB
    subgraph ControlRow [ ]
        direction LR
        User([👤 User])
        Agent["🔧 <b>SRE Agent</b><br/>(Orchestrator)"]
        Gemini{{"🧠 <b>Gemini 2.5 Pro</b>"}}

        User <==> Agent
        Agent <==> Gemini
    end

    subgraph Orchestration [Orchestrator Tools]
        direction LR
        TRIAGE["🛡️ Triage<br/>Analysis"]
        DEEP["🕵️ Deep Dive<br/>Analysis"]
        AGG_TOOL["📊 Aggregate<br/>Analysis"]
    end

    subgraph Specialists [Specialists]
        direction LR

        subgraph TraceExperts [📊 Trace Specialists]
            direction TB
            L["⏱️ Latency"]
            E["💥 Error"]
            S["🏗️ Structure"]
            ST["📉 Stats"]
            C["🔗 Causality"]
            SI["🌊 Impact"]
        end

        subgraph LogExperts [📝 Log Specialists]
            direction TB
            LP["🔍 Log Pattern<br/>Extractor"]
        end
    end

    subgraph ToolLayer [Integrated Tools]
        direction LR
        TraceAPI["☁️ Cloud Trace API"]
        LogAPI["📋 Cloud Logging"]
        MetricsAPI["📊 Cloud Monitoring"]
        BQ["🗄️ BigQuery"]
    end

    Agent ==> Orchestration
    Orchestration ==> Specialists
    Agent -.-> ToolLayer
    Specialists -.-> ToolLayer
    Orchestration -.-> ToolLayer

    style ControlRow fill:none,stroke:none
    style Squads fill:none,stroke:none

    classDef userNode fill:#ffffff,stroke:#000000,stroke-width:2px;
    classDef agentNode fill:#e3f2fd,stroke:#1565c0,stroke-width:2px;
    classDef brainNode fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,stroke-dasharray: 5 5;
    classDef squadNode fill:#fff8e1,stroke:#fbc02d,stroke-width:1px;
    classDef logNode fill:#e8f5e9,stroke:#43a047,stroke-width:1px;
    classDef toolNode fill:#f5f5f5,stroke:#616161,stroke-width:1px;

    class User userNode;
    class Agent agentNode;
    class Gemini brainNode;
    class AGG,L,E,S,ST,C,SI squadNode;
    class LP logNode;
    class TraceAPI,LogAPI,MetricsAPI,BQ toolNode;
```

### Interaction Workflow

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'darkMode': false, 'background': '#ffffff', 'mainBkg': '#ffffff', 'fontFamily': 'arial', 'fontSize': '16px', 'textColor': '#000000', 'primaryTextColor': '#000000'}}}%%
sequenceDiagram
    actor User
    participant SRE as 🔧 SRE Agent
    participant Orch as 🛡️ Orchestrator Tools
    participant Expert as 📊 Specialist Experts
    participant Tools as 🛠️ GCP Infrastructure

    Note over User, Tools: 🔎 PHASE 1: EVIDENCE GATHERING

    User->>SRE: 1. "Investigate high latency..."
    SRE->>Orch: 2. run_aggregate_analysis()
    Orch->>Tools: 3. Query BigQuery / Trace API
    Tools-->>Orch: 4. Health metrics + exemplar traces
    Orch-->>SRE: 5. Aggregate Findings

    Note over User, Tools: ⚡ PHASE 2: PARALLEL TRIAGE

    SRE->>Orch: 6. run_triage_analysis()
    activate Orch
    par Parallel Investigation
        Orch->>Expert: 7a. Latency Expert
        Orch->>Expert: 7b. Error Expert
        Orch->>Expert: 7c. Structure Expert
    end
    Expert-->>Orch: 8. Specialist insights
    Orch-->>SRE: 9. Unified Triage Report
    deactivate Orch

    SRE->>User: 10. "Found 3 new error patterns..."

    Note over User, Tools: 🕵️ PHASE 3: ROOT CAUSE

    User->>SRE: 11. "What's the root cause?"
    SRE->>Orch: 12. run_deep_dive_analysis()
    Orch->>Expert: 13. Causality + Impact Experts
    Expert-->>Orch: 14. Root cause identified
    Orch-->>SRE: 15. Deep Dive Findings

    Note over User, Tools: 📝 PHASE 4: REPORT

    SRE->>User: 16. 📂 Investigation Summary
```

## Features

### Core Capabilities

1. **Trace Analysis** (Primary Specialization)
   - Aggregate analysis using BigQuery (thousands of traces at scale)
   - Individual trace inspection via Cloud Trace API
   - Trace comparison (diff analysis) to identify what changed
   - Pattern detection (N+1 queries, serial chains, bottlenecks)
   - Root cause analysis through span-level investigation

2. **Log Analysis** (Enhanced with Drain3!)
   - **Pattern Extraction**: Compress thousands of logs into patterns using Drain3 algorithm
   - **Anomaly Detection**: Compare time periods to find NEW emergent log patterns
   - **Smart Extraction**: Automatically find the log message in any payload format
   - Query and analyze logs from Cloud Logging (MCP and direct API)
   - Correlate logs with traces for root cause evidence

3. **Metrics Analysis**
   - Query time series data from Cloud Monitoring (MCP and direct API)
   - PromQL queries for complex aggregations
   - Trend detection and anomaly identification

### Multi-Stage Trace Analysis Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  Stage 0: Aggregate Analysis (BigQuery)                         │
│  • Analyze thousands of traces                                  │
│  • Identify patterns, trends, problem services                  │
│  • Select exemplar traces (baseline + outliers)                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Stage 1: Triage (4 Parallel Analyzers)                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐│
│  │  Latency    │ │   Error     │ │  Structure  │ │ Statistics  ││
│  │  Analyzer   │ │  Analyzer   │ │  Analyzer   │ │  Analyzer   ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘│
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Stage 2: Deep Dive (2 Parallel Analyzers)                      │
│  ┌───────────────────────────┐ ┌───────────────────────────────┐│
│  │    Causality Analyzer     │ │  Service Impact Analyzer      ││
│  │    (Root Cause)           │ │  (Blast Radius)               ││
│  └───────────────────────────┘ └───────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
trace_analyzer/
├── gcp_observability/    # Main package
│   ├── agent.py          # SRE Agent & Orchestrator Tools
│   ├── prompt.py         # Agent instructions
│   ├── schema.py         # Pydantic structured output schemas
│   ├── tools/            # Modular tools for GCP & Analysis
│   │   ├── clients/      # Direct API Clients (Logging, Trace, Monitoring)
│   │   ├── mcp/          # MCP Integration (BigQuery, Logging, etc.)
│   │   ├── analysis/     # Analysis Logic (Trace, Logs, BigQuery)
│   │   └── common/       # Telemetry & Caching
│   └── sub_agents/       # Specialist Specialists
│       ├── trace.py      # Latency, Error, Structure experts
│       └── logs.py       # Log pattern extractor
├── tests/                # Comprehensive test suite
├── deploy/               # Deployment scripts for Agent Engine
└── pyproject.toml        # Project dependencies and ADK config
```

## Quick Start

### Prerequisites

- Python 3.10+
- Google Cloud SDK configured
- Access to a GCP project with Cloud Trace data

### Installation

```bash
# Install dependencies using uv
uv sync

# Copy and configure environment
cp .env.example .env
# Edit .env with your GCP project settings
```

### Environment Configuration

```bash
# Required: GCP project with telemetry data
GOOGLE_CLOUD_PROJECT=your-gcp-project

# Optional: Override trace project if different
TRACE_PROJECT_ID=your-trace-project

# Optional: Vertex AI settings
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_LOCATION=us-central1
```

### Running the Agent

```bash
# Interactive terminal
uv run adk run gcp_observability_agent

# Web interface
uv run adk web gcp_observability_agent
```

## Usage Examples

### Trace Analysis

```
# Analyze recent traces
"What's the health of the checkout-service in the last 24 hours?"

# Find performance issues
"Find slow traces and identify the root cause"

# Compare traces
"Compare trace abc123 with trace def456"

# BigQuery aggregate analysis
"Analyze traces in BigQuery dataset my_project.telemetry"
```

### Log Analysis

```
# Search for errors
"Find ERROR level logs in the last hour"

# Correlate with traces
"Get logs for trace abc123"

# Pattern extraction (NEW!)
"Extract log patterns from the last hour and show me the top error patterns"

# Anomaly detection (NEW!)
"Compare log patterns from 10am-11am vs 11am-12pm and find new error patterns"

# Incident investigation (NEW!)
"What new log patterns appeared in the checkout-service after the alert fired?"
```

### Metrics Analysis

```
# Query metrics
"Show CPU utilization for the frontend service"

# PromQL queries (NEW!)
"Query PromQL: rate(http_requests_total[5m])"
```

## Available Tools

### BigQuery Analysis Tools
| Tool | Description |
|------|-------------|
| `analyze_aggregate_metrics` | Service-level health metrics at scale using BigQuery |
| `find_exemplar_traces` | Find baseline and outlier traces for investigation |
| `compare_time_periods` | Detect performance regressions between two windows |
| `detect_trend_changes` | Identify exact time when metrics started degrading |
| `correlate_logs_with_trace` | SQL-based correlation between spans and logs |

### Cloud Trace Tools
| Tool | Description |
|------|-------------|
| `fetch_trace` | Get full trace by ID |
| `list_traces` | List traces with advanced filtering |
| `get_trace_by_url` | Parse Cloud Console URL to get trace |
| `find_example_traces` | Smart discovery of baseline vs anomaly traces |
| `calculate_span_durations` | Extract timing information for all spans |
| `extract_errors` | Find all error spans in a trace with details |
| `build_call_graph` | Build hierarchical call graph tree |
| `summarize_trace`| Compact summary of trace for LLM context |
| `validate_trace_quality` | Detect orphaned spans and clock skew |
| `compare_span_timings` | Compare two traces for timing slowdowns |
| `find_structural_differences` | Compare call graph topology changes |

### Cloud Logging Tools
| Tool | Description |
|------|-------------|
| `mcp_list_log_entries` | Query logs via MCP |
| `list_log_entries` | Query logs via direct API |
| `get_logs_for_trace` | Get logs correlated with a trace |
| `list_error_events` | List events from Error Reporting |

### Log Pattern Analysis Tools (NEW!)
| Tool | Description |
|------|-------------|
| `extract_log_patterns` | Compress logs into patterns using Drain3 |
| `compare_log_patterns` | Compare patterns between periods |
| `analyze_log_anomalies` | triage patterns focused on errors |

### Cloud Monitoring Tools
| Tool | Description |
|------|-------------|
| `mcp_list_timeseries` | Query metrics via MCP |
| `mcp_query_range` | Execute PromQL queries via MCP |
| `list_time_series` | Query metrics via direct API |
| `query_promql` | Execute PromQL queries via direct API |
| `get_current_time` | Utility to get current ISO timestamp |



## GCP Observability SRE Agent

An Agentic AI system for analyzing Google Cloud Observability data (Traces, Logs, Metrics) to identify root causes of production issues.

**New Architecture**: Consolidates `trace_analyzer` and `sre_agent` into a single `gcp_observability` library.

### Trace Analysis Squad
| Sub-Agent | Stage | Role |
|-----------|-------|------|
| `aggregate_analyzer` | 0 | **Data Analyst** - Analyzes BigQuery data to find trends and select exemplars. |
| `latency_analyzer` | 1 | **Latency Specialist** - Timing expert focusing on slowdowns and anti-patterns. |
| `error_analyzer` | 1 | **Error Forensics** - Failure detective identifying and comparing error spans. |
| `structure_analyzer` | 1 | **Structure Mapper** - Topology expert detecting structural changes in call graphs. |
| `statistics_analyzer` | 1 | **Quant Expert** - Determines statistical significance and percentile ranking. |
| `causality_analyzer` | 2 | **Root Cause Analyst** - Identifies the primary cause using evidence from traces/logs. |
| `service_impact_analyzer` | 2 | **Impact Assessor** - Determines blast radius and user impact. |

### Log Analysis Squad
| Sub-Agent | Role |
|-----------|------|
| `log_pattern_extractor`| **Log Whisperer** - Uses Drain3 to compress thousands of logs into patterns to find "spicy" anomalies. |

## Development

### Running Tests

```bash
uv run pytest
uv run pytest -v
```

### Code Quality

```bash
uv run ruff check gcp_observability/
```

## IAM Permissions

Required roles for the service account:

- `roles/cloudtrace.user` - Read traces
- `roles/logging.viewer` - Read logs
- `roles/monitoring.viewer` - Read metrics
- `roles/bigquery.dataViewer` - Query BigQuery (if using BigQuery tools)

## License

Apache-2.0
