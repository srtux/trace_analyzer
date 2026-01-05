# Cloud Trace Analyzer Agent

A Google ADK-based agent that performs diff analysis on distributed traces from Cloud Trace. Compare a baseline (normal) trace to an abnormal trace to identify performance regressions, errors, and behavioral changes.

## Features

- **Automatic Trace Discovery**: Finds example traces (fastest vs slowest) for comparison
- **Latency Analysis**: Identifies which spans got slower and by how much
- **Error Detection**: Finds new errors and changed error patterns
- **Structure Comparison**: Detects missing or new operations in the call graph
- **Statistical Analysis**: Calculates P50/P99 latencies, z-scores, and identifies anomalies
- **Root Cause Synthesis**: combines findings to explain what changed and why (causal analysis)

## Architecture

```
trace_analyzer_agent (Root Orchestrator)
├── latency_analyzer (Sub-Agent)
├── error_analyzer (Sub-Agent)
├── structure_analyzer (Sub-Agent)
├── statistics_analyzer (Sub-Agent)
├── causality_analyzer (Sub-Agent)
└── Tools:
    ├── find_example_traces
    ├── fetch_trace
    ├── list_traces
    └── get_trace_by_url
```

## Setup

### 1. Install Dependencies

```bash
cd trace_analyzer
uv sync
```

### 2. Configure Environment

Copy the example environment file and configure:

```bash
cp .env.example .env
```

Edit `.env` with your GCP configuration:

```bash
# For Vertex AI (recommended for production)
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=your-gcp-project
GOOGLE_CLOUD_LOCATION=us-central1

# Or for Google AI Studio
# GOOGLE_GENAI_USE_VERTEXAI=0
# GOOGLE_API_KEY=your-api-key
```

### 3. Ensure Cloud Trace Access

Make sure you have the `roles/cloudtrace.user` IAM role on the project you want to analyze.

## Usage

### Run with ADK CLI

```bash
# Terminal interface
cd trace_analyzer
uv run adk run .

# Web interface
uv run adk web
```

### Example Prompts

**Auto-discover and compare traces:**
```
Find example traces in my project and show me what's different between a fast and slow request.
```

**Compare specific traces:**
```
Compare trace abc123def456 (baseline) with trace xyz789abc123 (slow) in project my-gcp-project
```

**Analyze from Console URL:**
```
Analyze this trace: https://console.cloud.google.com/traces/list?project=my-project&tid=abc123
```

**Filter by service:**
```
Find traces from the payment-service in the last 2 hours and compare the fastest vs slowest
```

## Project Structure

```
trace_analyzer/
├── deploy/              # Deployment scripts
├── trace_analyzer/
│   ├── __init__.py
│   ├── agent.py         # Root agent definition
│   ├── prompt.py        # Root agent prompts
│   ├── schema.py        # Pydantic models
│   ├── sub_agents/
│   │   ├── latency/     # Latency comparison
│   │   ├── error/       # Error detection
│   │   ├── structure/   # Call graph analysis
│   │   ├── statistics/  # Statistical analysis & anomalies
│   │   └── causality/   # Root cause identification
│   └── tools/
│       ├── trace_client.py   # Cloud Trace API
│       └── trace_analysis.py # Analysis utilities
├── tests/
├── pyproject.toml
└── README.md
```

## License

Apache-2.0
