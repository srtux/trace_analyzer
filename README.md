# SRE Agent

[![Status](https://img.shields.io/badge/Status-Active-success)]()
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)]()
[![Framework](https://img.shields.io/badge/Framework-Google%20ADK-red)]()
[![GCP](https://img.shields.io/badge/Google%20Cloud-Native-4285F4)]()

**The world's most comprehensive SRE Agent for Google Cloud.** An ADK-based agent for analyzing telemetry data from Google Cloud Observability: **traces**, **logs**, **metrics**, **SLOs**, and **Kubernetes workloads**. Features include SLO/SLI framework integration, GKE debugging, and automated remediation suggestions.

## Architecture

The agent is built using the Google Agent Development Kit (ADK). It uses a **"Council of Experts"** orchestration pattern where the main **SRE Agent** coordinates specialized analysis through high-level orchestration tools.

### System Architecture

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'background': '#ffffff'}}}%%
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

        subgraph TraceExperts [Trace Specialists]
            direction TB
            L["⏱️ Latency"]
            E["💥 Error"]
            S["🏗️ Structure"]
            ST["📉 Stats"]
            C["🔗 Causality"]
            SI["🌊 Impact"]
            CP["🛤️ Critical<br/>Path"]
        end

        subgraph LogExperts [Log Specialists]
            direction TB
            LP["🔍 Log Pattern<br/>Extractor"]
        end

        subgraph MetricsExperts [Metrics Specialists]
            direction TB
            MA["📈 Metrics<br/>Analyzer"]
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
    style Specialists fill:none,stroke:none

    classDef userNode fill:#ffffff,stroke:#333,stroke-width:2px;
    classDef agentNode fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef brainNode fill:#f3e5f5,stroke:#4a148c,stroke-width:2px,stroke-dasharray: 5 5;
    classDef squadNode fill:#fff8e1,stroke:#fbc02d,stroke-width:1px;
    classDef logNode fill:#e8f5e9,stroke:#2e7d32,stroke-width:1px;
    classDef metricsNode fill:#e0f7fa,stroke:#006064,stroke-width:1px;
    classDef toolNode fill:#f5f5f5,stroke:#616161,stroke-width:1px;

    class User userNode;
    class Agent agentNode;
    class Gemini brainNode;
    class AGG_TOOL,L,E,S,ST,C,SI squadNode;
    class LP logNode;
    class MA metricsNode;
    class TraceAPI,LogAPI,MetricsAPI,BQ toolNode;
``````

### Interaction Workflow

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'background': '#ffffff'}}}%%
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

2. **Log Analysis**
   - **Pattern Extraction**: Compress thousands of logs into patterns using Drain3 algorithm
   - **Anomaly Detection**: Compare time periods to find new emergent log patterns
   - **Smart Extraction**: Automatically find the log message in any payload format
   - Query and analyze logs from Cloud Logging (MCP and direct API)
   - Correlate logs with traces for root cause evidence

3. **Metrics Analysis**
   - **Cross-Signal Correlation**: Correlate spikes in metrics with specific traces using exemplars
   - **PromQL**: Execute complex PromQL queries for aggregations and rates
   - **Trend Detection**: Identify statistical trends and anomalies in time series
   - **Service Health**: Monitor CPU, Memory, and custom metric signals

4. **Critical Path & Dependencies**
   - **Critical Path Analysis**: Identify the chain of spans driving latency
   - **Bottleneck Detection**: Pinpoint services on the critical path that contribute most to delay
   - **Dependency Mapping**: Automatically build service dependency graphs from traces
   - **Circular Dependency Detection**: Find dangerous feedback loops in service calls

5. **SLO/SLI Framework** (NEW!)
   - **Golden Signals**: Latency, Traffic, Errors, Saturation for any service
   - **SLO Status**: Current compliance and error budget remaining
   - **Error Budget Burn Rate**: Track how fast you're consuming your budget
   - **SLO Violation Prediction**: Will you breach your SLO in the next 24 hours?
   - **Incident Impact Analysis**: Quantify how much an incident cost your error budget

6. **GKE/Kubernetes Analysis** (NEW!)
   - **Cluster Health**: Node pool status, control plane health, active issues
   - **Node Pressure Detection**: CPU, memory, disk, PID pressure conditions
   - **Pod Restart Analysis**: Find OOMKilled containers and CrashLoopBackOff
   - **HPA Scaling Events**: Track autoscaler decisions and detect thrashing
   - **Trace-to-Pod Correlation**: Link traces to specific Kubernetes workloads

7. **Automated Remediation** (NEW!)
   - **Smart Suggestions**: Pattern-matched remediation recommendations
   - **Ready-to-Run Commands**: Generate gcloud commands for common fixes
   - **Risk Assessment**: Understand risk before making changes
   - **Similar Incident Lookup**: Learn from past incidents with similar patterns

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
sre_agent/
├── sre_agent/            # Main package
│   ├── agent.py          # SRE Agent & Orchestrator Tools
│   ├── prompt.py         # Agent instructions
│   ├── schema.py         # Pydantic structured output schemas
│   ├── tools/            # Modular tools for GCP & Analysis
│   │   ├── clients/      # Direct API Clients (Logging, Trace, Monitoring)
│   │   ├── mcp/          # MCP Integration (BigQuery, Logging, etc.)
│   │   ├── analysis/     # Analysis Logic (Trace, Logs, BigQuery, Metrics)
│   │   │   ├── trace/    # Trace analysis, comparison, filters
│   │   │   ├── logs/     # Log pattern extraction & matching
│   │   │   ├── metrics/  # Metrics statistics & anomalies
│   │   │   └── bigquery/ # BigQuery OTel analysis
│   │   └── common/       # Telemetry & Caching
│   └── sub_agents/       # Specialist Experts
│       ├── trace.py      # Latency, Error, Structure experts
│       ├── logs.py       # Log pattern extractor
│       └── metrics.py    # Metrics analyzer
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
uv run poe run

# Web interface
uv run poe web
```

### Modern Task Management (Recommended)

This project uses **Poe the Poet** for unified task management. All project scripts, deployment tasks, and tests are defined in `pyproject.toml`.

| Task | Command | Description |
|------|---------|-------------|
| **Sync** | `uv run poe sync` | Synchronize all dependencies with `uv` |
| **Deploy** | `uv run poe deploy` | **Safe Deploy**: Syncs docs, verifies imports, and deploys to Agent Engine |
| **List** | `uv run poe list` | List all deployed agents in Agent Engine |
| **Test** | `uv run poe test` | Run the full test suite |
| **Eval** | `uv run poe eval` | Run agent evaluations using ADK eval sets |
| **Delete** | `uv run poe delete --resource_id ID` | Delete a specific Agent Engine instance |
| **Pre-commit** | `uv run poe pre-commit` | Run all pre-commit hooks (lint, spell, check-added-large-files) |

Before deploying, ensure your `.env` file is configured with `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_STORAGE_BUCKET`.

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

### Trace Selection Tools
| Tool | Description |
|------|-------------|
| `select_traces_from_error_reports` | Discovery: find traces associated with recent Error Reporting events |
| `select_traces_from_monitoring_alerts` | Discovery: find traces linked to Cloud Monitoring incidents |
| `select_traces_from_statistical_outliers` | Discovery: find traces that are p99+ outliers for a service |
| `select_traces_manually` | User-driven: select traces by specific criteria or list of IDs |

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

**Architecture**: Refactored to use the modern "Council of Experts" orchestration pattern.

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
