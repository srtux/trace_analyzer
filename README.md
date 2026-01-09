# Cloud Trace Analyzer Agent

[![Status](https://img.shields.io/badge/Status-Active-success)]()
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)]()
[![Framework](https://img.shields.io/badge/Framework-Google%20ADK-red)]()


A Google ADK-based SRE assistant that performs sophisticated analysis on distributed traces using OpenTelemetry data. It combines BigQuery-powered aggregate analysis with detailed trace comparisons to identify performance regressions, errors, and behavioral changes.

## Features

- **Three-Stage Analysis Pipeline**:
  - **Stage 0 (Aggregate)**: BigQuery-powered analysis of thousands of traces to identify patterns and trends
  - **Stage 1 (Investigation)**: Comprehensive trace comparison analyzing latency, errors, structure, and statistics
  - **Stage 2 (Root Cause)**: Root cause analysis with service impact assessment
- **BigQuery OpenTelemetry Integration**: Native support for OpenTelemetry schema in BigQuery, enabling:
  - Aggregate metrics analysis (error rates, latency percentiles by service)
  - Trend detection (when did performance degrade?)
  - Time period comparison (before vs after)
  - Exemplar trace selection (find representative baseline and outlier traces)
  - Log correlation (find related logs for root cause analysis)
- **Streamlined Agent Architecture**: Uses **3 focused agents** (simplified from 7):
  - **Aggregate Analyzer**: BigQuery-powered data analyst
  - **Trace Investigator**: Comprehensive analysis of latency, errors, structure, and statistics
  - **Root Cause Analyzer**: Causality analysis and service impact assessment
- **SRE Pattern Detection**: Automatic detection of common distributed systems issues:
  - Retry storms (excessive retries indicating downstream issues)
  - Cascading timeouts (timeout propagation through service chains)
  - Connection pool exhaustion (long waits for connections)
- **Automatic Trace Discovery**: Intelligently identifies representative baseline (P50) and anomaly (P95 or error) traces
- **Advanced Trace Filtering**: Supports complex filters including service names, HTTP status codes, min/max latency, and custom attribute matching
- **Root Cause Synthesis**: Automatically identifies the critical path and performs causal analysis
- **Cloud Console Integration**: Directly analyze traces by pasting their Google Cloud Console URL

## Architecture

The agent is built using the Google Agent Development Kit (ADK). It uses a streamlined three-stage orchestration pattern where an **SRE Assistant** coordinates aggregate analysis, trace investigation, and root cause analysis.

### Analysis Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  Stage 0: Aggregate Analysis (BigQuery)                        │
│  • Analyze thousands of traces                                 │
│  • Identify patterns, trends, problem services                 │
│  • Select exemplar traces (baseline + outliers)                │
│  • Detect when issues started                                  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Stage 1: Investigation (Trace Investigator)                   │
│  • Compare baseline vs anomaly traces                          │
│  • Analyze latency, errors, structure, statistics              │
│  • Detect anti-patterns (N+1, serial chains, retry storms)     │
│  • Identify critical path bottlenecks                          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Stage 2: Root Cause (Root Cause Analyzer)                     │
│  • Causal analysis on critical path                            │
│  • Service impact and blast radius assessment                  │
│  • Log correlation for root cause evidence                     │
└─────────────────────────────────────────────────────────────────┘
```

### System Architecture

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#E8F0FE',
    'primaryTextColor': '#1967D2',
    'primaryBorderColor': '#1967D2',
    'lineColor': '#5F6368',
    'secondaryColor': '#F1F3F4',
    'tertiaryColor': '#F3E5F5',
    'fontFamily': 'inherit',
    'fontSize': '14px'
  }
}}%%
flowchart TB
    %% --- TOP ROW: USER -> AGENT -> GEMINI ---
    subgraph ControlRow [ ]
        direction LR
        User([👤 User])
        Agent["🔧 <b>Trace Analyzer Agent</b><br/>(SRE Assistant)"]
        Gemini{{"🧠 <b>Gemini Model</b>"}}

        User <==> Agent
        Agent <==> Gemini
    end

    %% --- MIDDLE ROW: SIMPLIFIED AGENTS ---
    subgraph Agents [ ]
        direction LR

        subgraph Stage1 [🔍 Investigation]
            direction TB
            TI["📊 <b>Trace Investigator</b><br/>Latency • Errors • Structure • Stats"]
        end

        subgraph Stage2 [🎯 Root Cause]
            direction TB
            RC["🔗 <b>Root Cause Analyzer</b><br/>Causality • Service Impact"]
        end
    end

    %% --- BOTTOM ROW: TOOLS ---
    subgraph ToolLayer [Integrated Tools]
        direction LR
        TraceAPI["☁️ Trace API"]
        BQ["🗄️ BigQuery MCP"]
        SRE["⚠️ SRE Patterns"]
    end

    %% --- CONNECTIONS ---
    Agent ==> Stage1
    Agent ==> Stage2

    %% Usage Flow (Dotted)
    Agent -.-> ToolLayer
    Stage1 -.-> ToolLayer
    Stage2 -.-> ToolLayer

    %% --- STYLING ---
    style ControlRow fill:none,stroke:none
    style Agents fill:none,stroke:none

    classDef userNode fill:#FFFFFF,stroke:#3C4043,stroke-width:2px,color:#3C4043;
    classDef agentNode fill:#1A73E8,stroke:#174EA6,stroke-width:2px,color:#FFFFFF;
    classDef brainNode fill:#F3E8FF,stroke:#9333EA,stroke-width:2px,stroke-dasharray: 5 5,color:#7E22CE;
    classDef squadNode fill:#E8F0FE,stroke:#1967D2,stroke-width:1px,color:#1967D2;
    classDef toolNode fill:#F1F3F4,stroke:#5F6368,stroke-width:1px,color:#3C4043;

    class User userNode;
    class Agent agentNode;
    class Gemini brainNode;
    class TI,RC squadNode;
    class TraceAPI,BQ,SRE toolNode;
```

### Interaction Workflow

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#E8F0FE',
    'primaryTextColor': '#1967D2',
    'primaryBorderColor': '#1967D2',
    'lineColor': '#5F6368',
    'fontFamily': 'inherit',
    'fontSize': '14px',
    'noteBkgColor': '#FEF7E0',
    'noteBorderColor': '#F9AB00',
    'noteTextColor': '#3C4043',
    'activationBkgColor': '#E8F0FE',
    'activationBorderColor': '#1967D2'
  }
}}%%
sequenceDiagram
    actor User
    participant Agent as 🔧 SRE Assistant
    participant Tools as 🛠️ Tools
    participant Inv as 🔍 Investigator
    participant RC as 🎯 Root Cause

    Note over User, RC: 📊 PHASE 1: DATA GATHERING

    User->>Agent: 1. "Analyze these traces..."
    Agent->>Tools: 2. Fetch Trace Data
    activate Tools
    Tools-->>Agent: 3. Trace Data
    deactivate Tools

    Note over User, RC: 🔍 PHASE 2: INVESTIGATION

    Agent->>Inv: 4. Run Investigation
    activate Inv
    Inv->>Inv: 5. Analyze Latency/Errors/Structure
    Inv-->>Agent: 6. Investigation Report
    deactivate Inv

    Agent->>User: 7. "Found performance issues..."

    Note over User, RC: 🎯 PHASE 3: ROOT CAUSE

    User->>Agent: 8. "Find the root cause"

    Agent->>RC: 9. Root Cause Analysis
    activate RC
    RC->>RC: 10. Causal Chain + Impact
    RC-->>Agent: 11. Root Cause Report
    deactivate RC

    Note over User, RC: 📝 PHASE 4: REPORT

    Agent->>User: 12. 📋 Analysis Report
```

### Core Components
- **SRE Assistant (Root)**: The orchestrator that coordinates analysis and synthesizes findings into actionable reports. Uses a streamlined three-stage workflow optimized for SRE troubleshooting.
- **Aggregate Analyzer (Stage 0)**: Uses BigQuery to analyze OpenTelemetry trace data at scale, identifying patterns, trends, and selecting exemplar traces.
- **Trace Investigator (Stage 1)**: Comprehensive analysis that identifies *what* is wrong by examining latency, errors, structure, and statistical patterns. Detects anti-patterns like N+1 queries, serial chains, and retry storms.
- **Root Cause Analyzer (Stage 2)**: Investigates *why* it happened (causality analysis) and *who* else is affected (service impact and blast radius assessment).
- **SRE Pattern Detection**: Automatic detection of common distributed systems issues including retry storms, cascading timeouts, and connection pool exhaustion.
- **Dynamic MCP Integration**: Uses `ApiRegistry` to lazily load BigQuery tools, ensuring cross-platform stability.

### OpenTelemetry BigQuery Schema Support

The agent expects traces to be exported to BigQuery using the OpenTelemetry schema:

**Required Table Structure** (example: `project.telemetry._AllSpans`):
- `trace_id`: Unique trace identifier
- `span_id`: Unique span identifier
- `parent_span_id`: Parent span reference
- `span_name`: Operation name
- `start_time`: Span start timestamp
- `end_time`: Span end timestamp
- `duration`: Span duration in nanoseconds
- `status_code`: OK, ERROR, UNSET
- `service_name`: Service identifier (from resource attributes)
- `attributes`: Key-value pairs (STRUCT or JSON)

**Optional Table for Logs** (example: `project.telemetry.otel_logs`):
- `trace_id`: Correlation with traces
- `timestamp`: Log timestamp
- `severity_text`: ERROR, WARN, INFO, etc.
- `body`: Log message
- `resource_attributes`: Service metadata

## Setup

### 1. Install Dependencies

The project uses `uv` for high-performance dependency management:

```bash
cd trace_analyzer
uv sync
```

### 2. Configure Environment

Copy the example environment file and configure your Google Cloud project:

```bash
cp .env.example .env
```

Key variables in `.env`:
```bash
# Required for Cloud Trace and BigQuery access
GOOGLE_CLOUD_PROJECT=your-gcp-project
GOOGLE_CLOUD_LOCATION=us-central1

# Agent Engine Configuration
GOOGLE_GENAI_USE_VERTEXAI=1
```

### 3. Ensure IAM Permissions

The authenticated user or service account requires:
- `roles/cloudtrace.user`
- `roles/bigquery.dataViewer`
- `roles/bigquery.jobUser`

## Deployment

### Deployment (Standard ADK CLI)
 
 If you prefer using the standard `adk` CLI, you can pass environment variables via an env file:
 
 ```bash
 # 1. Ensure env vars are in trace_analyzer/telemetry.env
 # 2. Deploy using the --env_file flag
 uv run adk deploy agent_engine \
   --project=your-project \
   --region=us-central1 \
   --staging_bucket=your-bucket \
   --display_name="Trace Analyzer" \
   --env_file trace_analyzer/telemetry.env \
   trace_analyzer
 ```
 
 ### Deployment (Custom Script)
 
 We also provide a custom deployment script that supports direct flags:
 
 ```bash
 # Basic deployment
 uv run python deploy/deploy.py --create
 ```

The script will create a Reasoning Engine (Agent Engine) resource and output its resource name.

## Usage

### Running the Agent

```bash
# Launch the interactive terminal UI
uv run adk run .

# Launch the web-based interface
uv run adk web
```

### Example Prompts

**SRE Investigation with BigQuery (Recommended):**
> "Analyze traces in my BigQuery dataset `myproject.telemetry` for the last 24 hours. Which services are having issues?"

> "Start broad: analyze aggregate metrics for the checkout-service, find when performance degraded, then deep-dive into exemplar traces."

> "Compare traces from yesterday (baseline) vs today (anomaly) for the payment-service."

**Quick Trace Comparison:**
> "Find example traces in my project from the last 4 hours and show me what's different between a typical request and a slow one."

**Specific Investigation:**
> "Analyze this trace from the production console: https://console.cloud.google.com/traces/details/[TRACE_ID]?project=[PROJECT_ID]"

**Service-Specific Filtering:**
> "Find traces for the 'payment-processor' service with latency > 500ms and compare them to the baseline."

**Root Cause with Log Correlation:**
> "Deep-dive into trace xyz789 and find correlated logs to identify the root cause."

**Trend Detection:**
> "Detect when the P95 latency started increasing for the user-service in the last 72 hours."

## Project Structure

```
trace_analyzer/
├── trace_analyzer/
│   ├── agent.py          # Root orchestrator (SRE Assistant)
│   ├── prompt_v2.py      # Streamlined SRE-focused prompts
│   ├── sub_agents/       # Specialized analysis agents
│   │   ├── aggregate/    # Stage 0: Aggregate Analyzer (BigQuery)
│   │   ├── investigator/ # Stage 1: Trace Investigator (consolidated)
│   │   └── root_cause/   # Stage 2: Root Cause Analyzer (consolidated)
│   ├── tools/
│   │   ├── bigquery_otel.py      # BigQuery OpenTelemetry analysis tools
│   │   ├── o11y_clients.py       # Shared Observability (Trace/Log/Error) Client
│   │   ├── trace_analysis.py     # Trace comparison and diffing tools
│   │   ├── statistical_analysis.py  # Statistical analysis tools
│   │   ├── sre_patterns.py       # SRE pattern detection (retry storms, timeouts, etc.)
│   │   └── trace_filter.py       # Advanced TraceQueryBuilder
│   └── schema.py         # Pydantic schemas for structured outputs
├── tests/                # Comprehensive test suite
├── deploy/               # Deployment scripts
├── AGENTS.md             # Developer & Contributor guide
├── pyproject.toml        # uv-based build configuration
└── README.md
```

## Reliability & Performance

- **Simplified Architecture**: Streamlined from 7 to 3 agents, reducing coordination overhead and improving execution speed.
- **Singleton MCP Pattern**: Uses `lru_cache` to prevent MCP session timeout issues in ASGI/uvicorn environments.
- **Observability**: Fully instrumented with OpenTelemetry for tracking tool execution and agent performance.
- **Truncation & Noise Reduction**: Advanced logging patterns ensure that large trace datasets don't overwhelm LLM context windows.
- **Scalable Analysis**: BigQuery integration allows analyzing millions of traces without overwhelming the Trace API.
- **SRE Pattern Detection**: Automatic detection of common issues (retry storms, cascading timeouts, pool exhaustion) for faster troubleshooting.

## BigQuery Setup (Optional but Recommended)

To enable the full SRE investigation workflow with aggregate analysis:

1. **Export traces to BigQuery**: Set up OpenTelemetry trace export to BigQuery
   - Use the [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/) with BigQuery exporter
   - Or use [Cloud Trace BigQuery export](https://cloud.google.com/trace/docs/trace-export)

2. **Configure BigQuery dataset**: Ensure your BigQuery dataset contains a table with the OpenTelemetry schema
   ```bash
   # Example dataset: myproject.telemetry
   # Example table: _AllSpans
   ```

3. **Grant BigQuery permissions**: Ensure the agent has access
   ```bash
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:SERVICE_ACCOUNT" \
     --role="roles/bigquery.dataViewer"
   ```

4. **Use aggregate analysis in prompts**:
   ```
   "Analyze traces in dataset myproject.telemetry for the last 24 hours"
   ```

**Note**: The agent works without BigQuery (using Cloud Trace API only), but BigQuery enables more sophisticated SRE workflows with aggregate analysis, trend detection, and exemplar selection at scale.

## Troubleshooting

- **`ValueError: stale session`**: This usually happens if the local database state gets out of sync with the running agent. Try clearing the `.adk` directory or restarting the server.
- **Permission Errors**: Ensure you have run `gcloud auth application-default login` and that your user has `roles/cloudtrace.user` and `roles/bigquery.dataViewer`.
- **ASGI Errors**: If you see "ASGI callable returned without completing response", ensure you are using the latest version of the ADK and that `LazyMcpRegistryToolset` is being used for MCP tools.

## Contributing

See [AGENTS.md](./AGENTS.md) for detailed developer workflows, testing instructions, and PR guidelines.

## License

Apache-2.0
