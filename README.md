# SRE Agent

[![Status](https://img.shields.io/badge/Status-Active-success)]()
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)]()
[![Framework](https://img.shields.io/badge/Framework-Google%20ADK-red)]()

An ADK-based agent for analyzing telemetry data from Google Cloud Observability: **traces**, **logs**, and **metrics**. Specializes in distributed trace analysis with multi-stage investigation capabilities.

## Features

### Core Capabilities

1. **Trace Analysis** (Primary Specialization)
   - Aggregate analysis using BigQuery (thousands of traces at scale)
   - Individual trace inspection via Cloud Trace API
   - Trace comparison (diff analysis) to identify what changed
   - Pattern detection (N+1 queries, serial chains, bottlenecks)
   - Root cause analysis through span-level investigation

2. **Log Analysis**
   - Query and analyze logs from Cloud Logging (MCP and direct API)
   - Correlate logs with traces for root cause evidence
   - Time-based analysis around incidents

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
sre_agent/
├── agent.py              # Main SRE Agent definition
├── prompt.py             # Agent prompts and instructions
├── schema.py             # Pydantic schemas for structured outputs
├── tools/
│   ├── common/           # Shared utilities
│   │   ├── decorators.py # @adk_tool with OTel instrumentation
│   │   ├── telemetry.py  # Telemetry helpers
│   │   └── cache.py      # Thread-safe caching
│   ├── gcp/              # GCP service tools
│   │   ├── mcp.py        # MCP toolset integration
│   │   └── clients.py    # Direct API clients
│   ├── trace/            # Trace analysis tools
│   │   ├── clients.py    # Cloud Trace API
│   │   ├── analysis.py   # Span analysis utilities
│   │   ├── comparison.py # Trace comparison
│   │   └── filters.py    # Query builders
│   └── bigquery/         # BigQuery analysis tools
│       └── otel.py       # OpenTelemetry schema queries
└── sub_agents/
    └── trace_analysis/   # Specialized trace sub-agents
        └── agents.py     # 7 sub-agents for multi-stage analysis
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
# Interactive terminal (new SRE Agent)
uv run adk run sre_agent

# Web interface
uv run adk web sre_agent

# Legacy trace_analyzer (still available)
uv run adk run trace_analyzer
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
```

### Metrics Analysis

```
# Query metrics
"Show CPU utilization for the frontend service"

# PromQL queries
"What's the rate of HTTP 5xx errors?"
```

## Available Tools

### BigQuery Tools
| Tool | Description |
|------|-------------|
| `analyze_aggregate_metrics` | Aggregate trace metrics |
| `find_exemplar_traces` | Find representative traces |
| `compare_time_periods` | Compare metrics between windows |
| `detect_trend_changes` | Find when metrics degraded |
| `correlate_logs_with_trace` | Find logs for a trace |

### Cloud Trace Tools
| Tool | Description |
|------|-------------|
| `fetch_trace` | Get full trace by ID |
| `list_traces` | List traces with filtering |
| `find_example_traces` | Smart trace discovery |
| `compare_span_timings` | Compare two traces |
| `find_structural_differences` | Compare structures |

### Cloud Logging Tools
| Tool | Description |
|------|-------------|
| `mcp_list_log_entries` | Query logs via MCP |
| `list_log_entries` | Query logs via API |
| `get_logs_for_trace` | Get logs for a trace |

### Cloud Monitoring Tools
| Tool | Description |
|------|-------------|
| `mcp_list_timeseries` | Query metrics via MCP |
| `mcp_query_range` | PromQL queries via MCP |
| `list_time_series` | Query metrics via API |

## Sub-Agents

| Sub-Agent | Stage | Role |
|-----------|-------|------|
| `aggregate_analyzer` | 0 | BigQuery analysis |
| `latency_analyzer` | 1 | Timing comparison |
| `error_analyzer` | 1 | Error detection |
| `structure_analyzer` | 1 | Topology analysis |
| `statistics_analyzer` | 1 | Outlier detection |
| `causality_analyzer` | 2 | Root cause |
| `service_impact_analyzer` | 2 | Blast radius |

## Development

### Running Tests

```bash
uv run pytest
uv run pytest -v
```

### Code Quality

```bash
uv run flake8 sre_agent/
```

## IAM Permissions

Required roles for the service account:

- `roles/cloudtrace.user` - Read traces
- `roles/logging.viewer` - Read logs
- `roles/monitoring.viewer` - Read metrics
- `roles/bigquery.dataViewer` - Query BigQuery (if using BigQuery tools)

## License

Apache-2.0
