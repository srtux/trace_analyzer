# SRE Agent Sub-Agents

This directory contains specialized sub-agents that form the "Council of Experts" orchestration pattern used by the main SRE Agent.

## Architecture Overview

The SRE Agent uses a multi-stage analysis pipeline where specialized sub-agents handle different aspects of investigation:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Stage 0: Aggregate Analysis (BigQuery)                              │
│  • aggregate_analyzer: Analyzes thousands of traces at scale         │
│  • Identifies trends, patterns, and selects exemplar traces          │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Stage 1: Triage (Parallel Execution)                                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    │
│  │  latency_   │ │   error_    │ │ structure_  │ │ statistics_ │    │
│  │  analyzer   │ │  analyzer   │ │  analyzer   │ │  analyzer   │    │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘    │
│                  ┌─────────────┐ ┌─────────────┐                     │
│                  │ resiliency_ │ │   log_      │                     │
│                  │ architect   │ │  analyst    │                     │
│                  └─────────────┘ └─────────────┘                     │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Stage 2: Deep Dive (Root Cause Investigation)                       │
│  ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐  │
│  │ causality_analyzer│ │service_impact_    │ │ change_detective  │  │
│  │ (Root Cause)      │ │analyzer (Blast R.)│ │ (Deploy Correl.)  │  │
│  └───────────────────┘ └───────────────────┘ └───────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Sub-Agent Files

| File | Sub-Agents | Description |
|------|------------|-------------|
| `trace.py` | 8 agents | Core trace analysis pipeline |
| `logs.py` | 1 agent | Log pattern analysis |
| `metrics.py` | 1 agent | Metrics analysis |
| `alerts.py` | 1 agent | Alert triage |
| `change.py` | 1 agent | Change correlation |

## Detailed Sub-Agent Descriptions

### Stage 0: Aggregate Analysis

#### `aggregate_analyzer` (trace.py)
- **Role**: Data Analyst
- **Persona**: "The Big Data Ninja"
- **Purpose**: Analyze fleet-wide patterns using BigQuery before diving into specific traces
- **Tools**: `analyze_aggregate_metrics`, `find_exemplar_traces`, `compare_time_periods`, `detect_trend_changes`

### Stage 1: Triage Squad

#### `latency_analyzer` (trace.py)
- **Role**: Latency Specialist
- **Persona**: "The Speed Demon"
- **Purpose**: Identify critical path and bottleneck spans
- **Tools**: `fetch_trace`, `calculate_span_durations`, `compare_span_timings`, `analyze_critical_path`

#### `error_analyzer` (trace.py)
- **Role**: Error Forensics Expert
- **Persona**: "Dr. Crash"
- **Purpose**: Diagnose error codes, stack traces, and failure patterns
- **Tools**: `fetch_trace`, `extract_errors`

#### `structure_analyzer` (trace.py)
- **Role**: Structure Mapper
- **Persona**: "The Architect"
- **Purpose**: Detect changes in call graph topology
- **Tools**: `fetch_trace`, `build_call_graph`, `find_structural_differences`

#### `statistics_analyzer` (trace.py)
- **Role**: Statistics Analyst
- **Persona**: "The Number Cruncher"
- **Purpose**: Calculate z-scores and determine statistical significance
- **Tools**: `fetch_trace`, `calculate_span_durations`, `compute_latency_statistics`, `detect_latency_anomalies`

#### `resiliency_architect` (trace.py)
- **Role**: Resiliency Architect
- **Persona**: "The Chaos Tamer"
- **Purpose**: Detect retry storms, cascading failures, and timeout issues
- **Tools**: `fetch_trace`, `build_call_graph`, `detect_circular_dependencies`

#### `log_analyst` (logs.py)
- **Role**: Log Analyst
- **Persona**: "The Log Whisperer"
- **Purpose**: Mine error patterns from logs using BigQuery SQL and Drain3
- **Tools**: `analyze_bigquery_log_patterns`, `extract_log_patterns`, `compare_time_periods`

### Stage 2: Deep Dive Investigators

#### `causality_analyzer` (trace.py)
- **Role**: Root Cause Analyst
- **Persona**: "The Consulting Detective"
- **Purpose**: Correlate findings across traces, logs, and metrics to find the "smoking gun"
- **Tools**: `fetch_trace`, `perform_causal_analysis`, `build_cross_signal_timeline`, `correlate_logs_with_trace`

#### `service_impact_analyzer` (trace.py)
- **Role**: Impact Assessor
- **Persona**: "The Blast Radius Expert"
- **Purpose**: Determine upstream/downstream impact and business consequences
- **Tools**: `fetch_trace`, `build_service_dependency_graph`, `analyze_upstream_downstream_impact`

#### `change_detective` (change.py)
- **Role**: Change Detective
- **Persona**: "The Time Traveler"
- **Purpose**: Correlate anomalies with recent deployments and configuration changes
- **Tools**: `list_log_entries`, `list_time_series`, `detect_trend_changes`

### Specialized Analysts

#### `metrics_analyzer` (metrics.py)
- **Role**: Metrics Expert
- **Purpose**: Analyze time-series data and detect metric anomalies
- **Tools**: `list_time_series`, `query_promql`, `detect_metric_anomalies`, `compare_metric_windows`

#### `alert_analyst` (alerts.py)
- **Role**: Alert Analyst
- **Persona**: "The First Responder"
- **Purpose**: Triage active alerts and identify "smoking gun" evidence
- **Tools**: `list_alerts`, `get_alert`, `list_alert_policies`

## Creating New Sub-Agents

To create a new sub-agent:

```python
from google.adk.agents import LlmAgent

MY_AGENT_PROMPT = """
Role: You are the **My Specialist** - Brief description.

### 🎯 Focus Areas
1. First focus area
2. Second focus area

### 🛠️ Tools
- `tool_name`: What it does

### 📝 Output Format
- **Key Finding**: Description
"""

my_agent = LlmAgent(
    name="my_agent",
    model="gemini-2.5-flash",
    description="Brief description for the orchestrator.",
    instruction=MY_AGENT_PROMPT,
    tools=[
        tool1,
        tool2,
    ],
)
```

## Orchestration Functions

The main agent uses these orchestration functions to invoke sub-agents:

| Function | Stage | Sub-Agents Invoked |
|----------|-------|-------------------|
| `run_aggregate_analysis` | 0 | `aggregate_analyzer` |
| `run_triage_analysis` | 1 | `latency_analyzer`, `error_analyzer`, `structure_analyzer`, `statistics_analyzer`, `resiliency_architect`, `log_analyst` |
| `run_deep_dive_analysis` | 2 | `causality_analyzer`, `service_impact_analyzer`, `change_detective` |
| `run_log_pattern_analysis` | Specialist | `log_analyst` |

## Design Principles

1. **Specialization**: Each sub-agent focuses on one aspect of analysis
2. **Parallelism**: Stage 1 and 2 sub-agents run in parallel
3. **Tool Isolation**: Each sub-agent only has access to relevant tools
4. **Persona-Driven**: Fun personas make outputs more engaging
5. **Structured Output**: Each agent returns consistent output formats
