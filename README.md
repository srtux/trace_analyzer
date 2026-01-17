# Auto SRE

[![Status](https://img.shields.io/badge/Status-Experimental-orange)]()
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)]()
[![Framework](https://img.shields.io/badge/Framework-Google%20ADK-red)]()
[![Frontend](https://img.shields.io/badge/Frontend-Flutter-02569B)]()
[![GCP](https://img.shields.io/badge/Google%20Cloud-Native-4285F4)]()
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![Tests](https://img.shields.io/badge/Tests-Passing-success)]()

**Auto SRE is an experimental SRE Agent for Google Cloud.** It analyzes telemetry data from Google Cloud Observability: **traces**, **logs**, **metrics**.

## Architecture

The agent is built using the Google Agent Development Kit (ADK). It uses a **"Council of Experts"** orchestration pattern where the main **SRE Agent** coordinates specialized analysis.

**Key Features:**
- **Trace-Centric Root Cause Analysis**: Prioritizes BigQuery for fleet-wide analysis.
- **Autonomous Investigation Pipeline**: Sequential workflow from signal detection to root cause synthesis.
- **Change Detective**: Correlates anomalies with deployments and config changes.
- **Alert Analyst**: The "First Responder" who triages active alerts and policies.
- **Resiliency Architect**: Detects architectural patterns like retry storms and cascading failures.
- **Friendly Expert Persona**: Combines deep technical expertise with a fun, approachable response style. 🕵️‍♂️✨
- **Tool Call Visualization**: Deep visibility into agent thinking with real-time "Running/Completed/Error" states for every tool call.
- **Investigation Persistence**: Automatic sync and storage of investigation sessions with Firestore support.
- **Multi-Session History**: View, load, and manage previous investigations through the Mission Control history panel.

### System Architecture

![System Architecture](architecture.jpg)

<details>
<summary>Mermaid Diagram Source</summary>

```mermaid
graph TD
    %% Styling
    classDef agent fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef subagent fill:#e0f2f1,stroke:#00695c,stroke-width:2px;
    classDef llm fill:#f3e5f5,stroke:#4a148c,stroke-width:2px;
    classDef tool fill:#fff3e0,stroke:#e65100,stroke-width:1px;
    classDef user fill:#fff,stroke:#333,stroke-width:2px;
    classDef orchestration fill:#fff9c4,stroke:#fbc02d,stroke-width:2px,stroke-dasharray: 5 5;

    %% User Layer
    User((User)) --> SRE_Agent

    %% Main Agent Layer
    subgraph "Orchestration Layer"
        SRE_Agent["SRE Agent<br/>(Manager)"]:::agent
        LLM["Gemini 2.5 Flash<br/>(LLM)"]:::llm
        SRE_Agent <--> LLM
    end

    %% Orchestration Tools (The bridge to sub-agents)
    subgraph "Orchestration Tools"
        RunAgg[run_aggregate_analysis]:::orchestration
        RunTriage[run_triage_analysis]:::orchestration
        RunDeep[run_deep_dive_analysis]:::orchestration
        RunLog[run_log_pattern_analysis]:::orchestration
    end

    SRE_Agent --> RunAgg
    SRE_Agent --> RunTriage
    SRE_Agent --> RunDeep
    SRE_Agent --> RunLog

    %% Sub-Agents (Council of Experts)
    subgraph "Council of Experts (Sub-Agents)"
        direction TB

        subgraph "Stage 0: Analysis"
            Aggregate["Aggregate Analyzer<br/>(Data Analyst)"]:::subagent
            Alert["Alert Analyst<br/>(First Responder)"]:::subagent
        end

        subgraph "Stage 1: Triage (Parallel)"
            Latency[Latency Specialist]:::subagent
            Error[Error Detective]:::subagent
            Structure[Structure Mapper]:::subagent
            Statistics[Statistics Analyst]:::subagent
            Resiliency[Resiliency Architect]:::subagent
        end

        subgraph "Stage 2: Deep Dive"
            Causality[Causality Expert]:::subagent
            Impact[Impact Assessor]:::subagent
            Change[Change Detective]:::subagent
        end

        subgraph "Specialists"
            LogPattern[Log Pattern Extractor]:::subagent
            Metrics[Metrics Analyzer]:::subagent
        end
    end

    %% Orchestration Flow
    RunAgg --> Aggregate
    SRE_Agent --> Alert
    RunTriage --> Latency & Error & Structure & Statistics & Resiliency
    RunDeep --> Causality & Impact & Change
    RunLog --> LogPattern
    SRE_Agent -- "Direct Delegation" --> Metrics

    %% Tools Layer
    subgraph "Tooling Ecosystem"
        direction TB

        subgraph "GCP Observability APIs"
            TraceAPI[Cloud Trace API]:::tool
            LogAPI[Cloud Logging API]:::tool
            MonitorAPI[Cloud Monitoring API]:::tool
            AlertAPI[Cloud Alerts API]:::tool
        end

        subgraph "Analysis Engines"
            BigQuery[BigQuery Engine]:::tool
            Drain3[Drain3 Pattern Engine]:::tool
            StatsEngine[Statistical Engine]:::tool
            GraphEngine["Graph/Topology Engine"]:::tool
        end

        subgraph "Model Context Protocol (MCP)"
            MCP_BQ[MCP BigQuery]:::tool
            MCP_Logs[MCP Logging]:::tool
            MCP_Metrics[MCP Monitoring]:::tool
        end

        subgraph "Domain Capabilities"
            SLO_Tools["SLO/SLI Tools"]:::tool
            K8s_Tools["GKE/Kubernetes Tools"]:::tool
            Remediation[Remediation Tools]:::tool
            Depend_Tools[Dependency Tools]:::tool
        end
    end

    %% Tool Usage Connections
    Aggregate --> BigQuery & TraceAPI & Depend_Tools
    Alert --> AlertAPI & MonitorAPI
    Latency --> TraceAPI & StatsEngine & Depend_Tools
    Error --> TraceAPI
    Structure --> GraphEngine & TraceAPI
    Statistics --> StatsEngine & TraceAPI
    Resiliency --> GraphEngine & TraceAPI
    Causality --> TraceAPI & LogAPI & MonitorAPI & GraphEngine & Depend_Tools
    Impact --> GraphEngine & TraceAPI & Depend_Tools
    Change --> LogAPI & MonitorAPI & StatsEngine
    LogPattern --> Drain3 & LogAPI
    Metrics --> MonitorAPI & MCP_Metrics & StatsEngine

    %% Main Agent Direct Tool Access
    SRE_Agent --> TraceAPI & LogAPI & MonitorAPI & AlertAPI
    SRE_Agent --> MCP_BQ & MCP_Logs & MCP_Metrics
    SRE_Agent --> SLO_Tools & K8s_Tools & Remediation
```

</details>

### Interaction Workflow

![Interaction Workflow](flow.jpg)

<details>
<summary>Mermaid Diagram Source</summary>

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant SRE as 🔧 SRE Agent
    participant Orch as 🛡️ Orchestrator
    participant Squad as 📊 Specialist Squad
    participant Cloud as ☁️ GCP Infra

    rect rgba(0, 0, 0, 0.1)
        Note over User, Cloud: 🔎 PHASE 1: GATHERING
        User->>SRE: "Why is latency high?"
        SRE->>Orch: Aggregate Analysis
        Orch->>Squad: Delegate to Data Analyst
        Squad->>Cloud: Fetch Health Metrics
        Cloud-->>Squad: Metrics + Exemplars
        Squad-->>Orch: Analysis Report
    end

    rect rgba(0, 0, 0, 0.1)
        Note over User, Cloud: ⚡ PHASE 2: TRIAGE
        SRE->>Orch: Start Triage
        par Parallel Analysis
            Orch->>Squad: Analyze Latency
            Squad->>Cloud: Fetch Trace Data
            Cloud-->>Squad: Traces
            Orch->>Squad: Analyze Errors
            Squad->>Cloud: Fetch Logs
            Cloud-->>Squad: Logs
            Orch->>Squad: Analyze Structure
        end
        Squad-->>Orch: Anomalies Detected
        Orch-->>SRE: Unified Report
    end

    rect rgba(0, 0, 0, 0.1)
        Note over User, Cloud: 🕵️ PHASE 3: ROOT CAUSE (Autonomous)
        Note over SRE: SRE Agent decides to investigate anomalies
        SRE->>Orch: Deep Dive
        Orch->>Squad: Causality Analysis
        Squad->>Cloud: Correlate Signals
        Cloud-->>Squad: Correlation Data
        Squad-->>Orch: Root Cause Identified
        SRE->>User: 📂 Full Investigation Summary
    end
```

</details>

## Features

### Core Capabilities

1.  **Trace Analysis** (Primary Specialization)
    *   Aggregate analysis using BigQuery (thousands of traces at scale)
    *   Individual trace inspection via Cloud Trace API
    *   Trace comparison (diff analysis) to identify what changed
    *   Pattern detection (N+1 queries, serial chains, bottlenecks)
    *   Root cause analysis through span-level investigation

2.  **Log Analysis**
    *   **Pattern Extraction**: Compress thousands of logs into patterns using Drain3 algorithm
    *   **Anomaly Detection**: Compare time periods to find new emergent log patterns
    *   **Smart Extraction**: Automatically find the log message in any payload format
    *   Query and analyze logs from Cloud Logging (MCP and direct API)
    *   Correlate logs with traces for root cause evidence

3.  **Metrics Analysis**
    *   **Cross-Signal Correlation**: Correlate spikes in metrics with specific traces using exemplars
    *   **PromQL**: Execute complex PromQL queries for aggregations and rates
    *   **Trend Detection**: Identify statistical trends and anomalies in time series
    *   **Service Health**: Monitor CPU, Memory, and custom metric signals
    *   **GCP Metrics Knowledge Base**: Built-in knowledge of best-practice metrics for GKE, Cloud Run, Vertex AI, BigQuery, and Cloud Logging.

4.  **Critical Path & Dependencies**
    *   **Critical Path Analysis**: Identify the chain of spans driving latency
    *   **Bottleneck Detection**: Pinpoint services on the critical path that contribute most to delay
    *   **Dependency Mapping**: Automatically build service dependency graphs from traces
    *   **Circular Dependency Detection**: Find dangerous feedback loops in service calls

5.  **SLO/SLI Framework** (NEW!)
    *   **Golden Signals**: Latency, Traffic, Errors, Saturation for any service
    *   **SLO Status**: Current compliance and error budget remaining
    *   **Error Budget Burn Rate**: Track how fast you're consuming your budget
    *   **SLO Violation Prediction**: Will you breach your SLO in the next 24 hours?
    *   **Incident Impact Analysis**: Quantify how much an incident cost your error budget

6.  **GKE/Kubernetes Analysis** (NEW!)
    *   **Cluster Health**: Node pool status, control plane health, active issues
    *   **Node Pressure Detection**: CPU, memory, disk, PID pressure conditions
    *   **Pod Restart Analysis**: Find OOMKilled containers and CrashLoopBackOff
    *   **HPA Scaling Events**: Track autoscaler decisions and detect thrashing
    *   **Trace-to-Pod Correlation**: Link traces to specific Kubernetes workloads

7.  **Automated Remediation** (NEW!)
    *   **Smart Suggestions**: Pattern-matched remediation recommendations
    *   **Ready-to-Run Commands**: Generate gcloud commands for common fixes
    *   **Risk Assessment**: Understand risk before making changes.

8.  **Alerting & Incident Response**
    *   **Active Alert Triage**: List and prioritize active Cloud Monitoring alerts
    *   **Policy Mapping**: Link alerts to their defining policies
    *   **First Responder**: "Smoking gun" evidence for starting investigations

9.  **Session Management & History** (NEW!)
    *   **Investigation History**: Automatic background syncing of conversations to persistent storage.
    *   **Firestore Integration**: Scalable session storage for Cloud Run deployments.
    *   **Local Persistence**: Automated local filesystem storage for development environments.
    *   **Stateful Context**: Backend maintains full conversation context across session reloads.
    *   **User Preferences**: Persistent storage of project selections and tool configurations.

10. **Web Dashboard (Mission Control)**
    *   **GenAI Interface**: A modern Chat UX powered by **Flutter** and **GenUI**.
    *   **Generative UI**: Dynamic Flutter widgets generated on-the-fly for traces, logs, and metrics.
    *   **Tool Execution Logs**: Integrated visual debugger showing the status, arguments, and results of every tool invocation.
    *   **Interactive Visualizations**: Trace waterfalls, log clusters, and metric charts.
    *   **Canvas Widgets**: Advanced real-time visualizations including:
        - **Agent Activity Canvas**: Animated workflow visualization showing agent coordination
        - **Service Topology Canvas**: Interactive dependency graph with health indicators
        - **Incident Timeline Canvas**: Event correlation and root cause timeline
        - **Metrics Dashboard Canvas**: Multi-metric grid with sparklines and anomaly alerts
        - **AI Reasoning Canvas**: Agent thought process with confidence scores
    *   **Full Source**: Located in `autosre/` directory. See [autosre/README.md](autosre/README.md) for details.

10. **Session Management & Persistence**
    *   **ADK Sessions**: Conversation history managed by ADK SessionService
    *   **Session History Panel**: View and switch between previous investigations
    *   **Auto-Backend Selection**: Uses `DatabaseSessionService` (SQLite) locally, `VertexAiSessionService` on Agent Engine
    *   **User Preferences**: Persistent project selection and tool configuration
    *   **Multi-Backend Storage**: File-based JSON locally, Firestore on Cloud Run

### Multi-Stage Trace Analysis Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  Stage 0: Analysis (BigQuery)                                   │
│  • Analyze thousands of traces                                  │
│  • Identify patterns, trends, problem services                  │
│  • Select exemplar traces (baseline + outliers)                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Stage 1: Triage (5 Parallel Analyzers)                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐│
│  │  Latency    │ │   Error     │ │  Structure  │ │ Statistics  ││
│  │  Analyzer   │ │  Analyzer   │ │  Analyzer   │ │  Analyzer   ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘│
│                  ┌─────────────┐                                │
│                  │ Resiliency  │                                │
│                  │ Architect   │                                │
│                  └─────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Stage 2: Deep Dive (3 Parallel Analyzers)                      │
│  ┌───────────────────────────┐ ┌───────────────────────────────┐│
│  │    Causality Analyzer     │ │  Service Impact Analyzer      ││
│  │    (Root Cause)           │ │  (Blast Radius)               ││
│  └───────────────────────────┘ └───────────────────────────────┘│
│  ┌───────────────────────────┐                                  │
│  │    Change Detective       │                                  │
│  │    (Deploy Correlation)   │                                  │
│  └───────────────────────────┘                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
sre_agent/
├── sre_agent/            # Main package
│   ├── agent.py          # SRE Agent & Orchestrator Tools
│   ├── prompt.py         # Agent instructions
│   ├── schema.py         # Pydantic structured output schemas
│   ├── services/         # Backend services
│   │   ├── session.py    # ADK Session management
│   │   └── storage.py    # User preferences storage
│   ├── tools/            # Modular tools for GCP & Analysis
│   │   ├── clients/      # Direct API Clients (Logging, Trace, Monitoring)
│   │   ├── mcp/          # MCP Integration (BigQuery, Logging, etc.)
│   │   ├── analysis/     # Analysis Logic (Trace, Logs, BigQuery, Metrics)
│   │   │   ├── trace/    # Trace analysis, comparison, filters
│   │   │   ├── logs/     # Log pattern extraction & matching
│   │   │   ├── metrics/  # Metrics statistics & anomalies
│   │   │   └── bigquery/ # BigQuery OTel analysis
│   │   ├── genui_adapter.py # Adapter for GenUI/Flutter schema transformation
│   │   └── common/       # Telemetry & Caching
│   └── sub_agents/       # Specialist Experts
│       ├── trace.py      # Latency, Error, Structure experts
│       ├── logs.py       # Log pattern extractor
│       └── metrics.py    # Metrics analyzer
├── autosre/              # Flutter Web Frontend (Mission Control)
│   ├── lib/              # Flutter application code
│   │   ├── agent/        # Agent interaction logic
│   │   ├── models/       # Data models
│   │   ├── widgets/      # GenUI widgets (Trace Waterfall, Charts)
│   │   │   └── canvas/   # Canvas-style dynamic visualizations
│   │   └── main.dart     # Entry point
│   ├── web/              # Web entrypoint and assets
│   ├── test/             # Widget tests
│   └── pubspec.yaml      # Flutter dependencies
├── tests/                # Comprehensive test suite
├── deploy/               # Deployment scripts for Agent Engine
└── pyproject.toml        # Project dependencies and ADK config
```

## Quick Start

### Prerequisites

*   Python 3.10+
*   Google Cloud SDK configured
*   Access to a GCP project with Cloud Trace data

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
# Run the full stack (Backend + Frontend) [Recommended]
uv run poe dev
```

#### Manual Startup (Separate Processes)

If you need to run the components independently (e.g., for faster frontend hot-reloads):

**1. Backend (SRE Agent API)**
```bash
# From the project root
uv run poe web
```
*Starts the FastAPI/ADK backend on `http://127.0.0.1:8001`.*

**2. Frontend (Flutter Dashboard)**
```bash
# From the project root (via project script)
cd autosre
flutter run -d chrome --web-port 8080
```
*Starts the Flutter web UI on `http://localhost:8080`.*

#### Interactive Terminal Mode
```bash
uv run poe run
```


### Modern Task Management (Recommended)

This project uses **Poe the Poet** for unified task management. All project scripts, deployment tasks, and tests are defined in `pyproject.toml`.

| Task | Command | Description |
|------|---------|-------------|
| **Sync** | `uv run poe sync` | Synchronize all dependencies with `uv` |
| **Deploy (Backend)** | `uv run poe deploy` | **Safe Deploy**: Syncs docs, verifies imports, and deploys to Vertex Agent Engine |
| **Deploy (Frontend)** | `uv run poe deploy-web` | Optimized multi-stage build (Flutter Web) and deployment to Cloud Run |
| **Deploy (Full Stack)** | `uv run poe deploy-all` | One-container deployment of both API and Flutter Web to Cloud Run |
| **List** | `uv run poe list` | List all deployed agents in Agent Engine |
| **Test** | `uv run poe test` | Run the full test suite |
| **Eval** | `uv run poe eval` | Run agent evaluations using ADK eval sets |
| **Delete** | `uv run poe delete --resource_id ID` | Delete a specific Agent Engine instance |
| **Pre-commit** | `uv run poe pre-commit` | Run all pre-commit hooks (lint, spell, check-added-large-files) |

### Deployment

#### 1. Unified Full Stack Deployment (Recommended)
The easiest way to deploy the entire system:
```bash
uv run poe deploy-all
```

For detailed instructions on architecture, IAM roles, and individual script usage, see the **[Detailed Deployment Guide (deploy/README.md)](deploy/README.md)**.

### Deployment Summary:
1. Deploys the **Backend** ADK Agent to Vertex AI Agent Engine.
2. Deploys the **Unified Dashboard** (Flutter Web + FastAPI Proxy) to Cloud Run.
3. Automatically wires the Frontend to the Backend via the `SRE_AGENT_ID` environment variable.

#### 2. Configuration & Versioning
Before deploying, ensure you have:
1. Created a Gemini API key secret:
   ```bash
   echo -n "your-api-key" | gcloud secrets create gemini-api-key --data-file=-
   ```
2. Granted the Secret Accessor role to your Cloud Run service account.

You can override deployment settings without changing your `.env` file:
```bash
# Point a new frontend to an existing specific backend version
uv run poe deploy-web --agent-url https://us-central1-aiplatform.googleapis.com/...
```

#### 2. Individual Component Deployment
If you only need to update one part of the stack:

*   **Backend Only**: `uv run poe deploy`
*   **Web/Unified Only**: `uv run poe deploy-web` (automatically mounts `gemini-api-key`)

#### 3. Configuration & Versioning
You can override deployment settings without changing your `.env` file:
```bash
# Point a new frontend to an existing specific backend version
uv run poe deploy-web --agent-url https://us-central1-aiplatform.googleapis.com/...
```

Before deploying, ensure your `.env` file is configured with your GCP project settings.

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

### Alert Analysis

```
# List active alerts
"Are there any active alerts?"

# List alert policies
"List all alert policies"
```

### Log Analysis

```
# Search for errors
"Find ERROR level logs in the last hour"

# Correlate with traces
"Get logs for trace abc123"

# Pattern extraction
"Extract log patterns from the last hour and show me the top error patterns"

# Anomaly detection
"Compare log patterns from 10am-11am vs 11am-12pm and find new error patterns"

# Incident investigation
"What new log patterns appeared in the checkout-service after the alert fired?"
```

### Metrics Analysis

```
# Query metrics
"Show CPU utilization for the frontend service"

# PromQL queries
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
| `compute_latency_statistics` | Calculate p50, p90, p99 for a set of traces |
| `detect_latency_anomalies` | Identify spans with statistically significant delay |

### Cloud Logging Tools
| Tool | Description |
|------|-------------|
| `mcp_list_log_entries` | Query logs via MCP |
| `list_log_entries` | Query logs via direct API |
| `get_logs_for_trace` | Get logs correlated with a trace |
| `list_error_events` | List events from Error Reporting |

### Log Pattern Analysis Tools
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
| `detect_metric_anomalies` | Identify sudden spikes or drops in metrics |
| `compare_metric_windows` | Compare metric distributions between two periods |
| `calculate_series_stats` | Calculate mean, stddev, and z-score for time series |
| `get_current_time` | Utility to get current ISO timestamp |

### Alerting Tools
| Tool | Description |
|------|-------------|
| `list_alerts` | List active alerts from Cloud Monitoring |
| `get_alert` | Get details of a specific alert |
| `list_alert_policies` | List alert policies |


### Critical Path & Dependency Tools
| Tool | Description |
|------|-------------|
| `analyze_critical_path`| Identify the sequence of spans determining total duration |
| `calculate_critical_path_contribution`| Quantify how much each span contributes to latency |
| `find_bottleneck_services`| Identify services appearing most frequently on critical paths |
| `build_service_dependency_graph`| Map upstream/downstream relationships between services |
| `detect_circular_dependencies`| Find cycles in the service call graph |
| `find_hidden_dependencies`| Detect services that are reached but not explicitly defined |

### Cross-Signal Analysis Tools
| Tool | Description |
|------|-------------|
| `correlate_trace_with_metrics`| Overlay trace span times on metric charts |
| `correlate_metrics_with_traces_via_exemplars`| Find traces that explain a metric spike |
| `build_cross_signal_timeline`| Create a unified timeline of traces, logs, and metrics |
| `analyze_signal_correlation_strength`| Statistically measure how strongly two signals are related |

### SLO/SLI Tools (NEW!)
| Tool | Description |
|------|-------------|
| `list_slos`| List all SLOs defined in a project or service |
| `get_slo_status`| Get current SLO compliance and error budget status |
| `analyze_error_budget_burn`| Calculate burn rate and predict budget exhaustion |
| `get_golden_signals`| Get the 4 SRE golden signals for a service |
| `correlate_incident_with_slo_impact`| Quantify incident impact on error budget |
| `predict_slo_violation`| Predict if current error rate will exhaust budget |

### GKE/Kubernetes Tools (NEW!)
| Tool | Description |
|------|-------------|
| `get_gke_cluster_health`| Get comprehensive GKE cluster health status |
| `analyze_node_conditions`| Check for CPU/memory/disk/PID pressure on nodes |
| `get_pod_restart_events`| Find pods with high restart counts |
| `analyze_hpa_events`| Analyze HPA scaling decisions and thrashing |
| `get_container_oom_events`| Find OOMKilled containers |
| `correlate_trace_with_kubernetes`| Link traces to Kubernetes pods |
| `get_workload_health_summary`| Health summary for all workloads in a namespace |

### Remediation Tools (NEW!)
| Tool | Description |
|------|-------------|
| `generate_remediation_suggestions`| Get smart fix recommendations based on findings |
| `get_gcloud_commands`| Generate ready-to-run gcloud commands |
| `estimate_remediation_risk`| Assess risk level of proposed changes |
| `find_similar_past_incidents`| Find past incidents with similar patterns |

## GCP Observability SRE Agent

An Agentic AI system for analyzing Google Cloud Observability data (Traces, Logs, Metrics) to identify root causes of production issues.

**Architecture**: Refactored to use the modern "Council of Experts" orchestration pattern. Powered by **Gemini 2.5 Flash** for high-speed, cost-effective analysis.

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
| `change_detective` | 2 | **Change Detective** - Correlates anomalies with deployments and config changes. |

### Triage Extensions
| Sub-Agent | Role |
|-----------|------|
| `resiliency_architect` | **Resiliency Architect** - Detects retry storms and cascading failures. |

### Log Analysis Squad
| Sub-Agent | Role |
|-----------|------|
| `log_analyst`| **Log Analyst** - Uses BigQuery SQL Regex (for scale) and Drain3 (for precision) to cluster logs. |

### Alert Analysis Squad
| Sub-Agent | Role |
|-----------|------|
| `alert_analyst`| **Alert Analyst** - The "First Responder" who triages active alerts and policies. |

### Metrics Analysis Squad
| Sub-Agent | Role |
|-----------|------|
| `metrics_analyzer`| **Metrics Expert** - Analyzes time-series data, detects anomalies, and performs cross-signal correlation. |

## Development

### Running Tests

```bash
uv run poe test
```

### Code Quality

 ```bash
 # Run pre-commit checks (ruff, codespell, etc.)
 uv run poe pre-commit

 # Manual lint and format
 uv run ruff check sre_agent/
 ```

## IAM Permissions

Required roles for the service account:

- `roles/cloudtrace.user` - Read traces
- `roles/logging.viewer` - Read logs
- `roles/monitoring.viewer` - Read metrics
- `roles/bigquery.dataViewer` - Query BigQuery (if using BigQuery tools)

## CI/CD Pipeline

The project uses **GitHub Actions** for automated testing and deployment.
See [.github/CICD.md](.github/CICD.md) for detailed configuration and secret requirements.

## License

Apache-2.0
