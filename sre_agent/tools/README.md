# SRE Agent Tools

This directory contains all the tools used by the SRE Agent for analyzing Google Cloud Observability data.

## Directory Structure

```
tools/
├── analysis/           # Analysis logic modules
│   ├── bigquery/       # BigQuery-based analysis (OTel, Logs)
│   ├── correlation/    # Cross-signal correlation tools
│   ├── logs/           # Log pattern extraction (Drain3)
│   ├── metrics/        # Metrics statistical analysis
│   ├── remediation/    # Remediation suggestions
│   └── trace/          # Trace analysis and comparison
├── bigquery/           # BigQuery client and query builders
├── clients/            # Direct GCP API clients
│   ├── alerts.py       # Cloud Monitoring Alerts
│   ├── gke.py          # GKE/Kubernetes
│   ├── logging.py      # Cloud Logging
│   ├── monitoring.py   # Cloud Monitoring
│   ├── slo.py          # Service Level Objectives
│   └── trace.py        # Cloud Trace
├── common/             # Shared utilities
│   ├── cache.py        # Result caching
│   ├── decorators.py   # @adk_tool decorator
│   └── telemetry.py    # OpenTelemetry setup
├── discovery/          # Telemetry source discovery
├── mcp/                # Model Context Protocol integrations
├── config.py           # Tool configuration management
├── reporting.py        # Report synthesis tools
└── test_functions.py   # Runtime connectivity checks
```

## Tool Categories

### 1. Trace Analysis Tools
Tools for analyzing distributed traces from Cloud Trace API and BigQuery.

| Tool | Description |
|------|-------------|
| `fetch_trace` | Retrieve a complete trace by ID |
| `list_traces` | List traces with filtering |
| `calculate_span_durations` | Calculate timing for all spans |
| `extract_errors` | Find error spans in a trace |
| `build_call_graph` | Build hierarchical call tree |
| `compare_span_timings` | Compare timing between two traces |

### 2. BigQuery Analysis Tools
Tools for fleet-wide analysis using BigQuery and OpenTelemetry data.

| Tool | Description |
|------|-------------|
| `analyze_aggregate_metrics` | Service-level health metrics at scale |
| `find_exemplar_traces` | Find baseline and outlier traces |
| `compare_time_periods` | Detect performance regressions |
| `detect_trend_changes` | Identify when metrics started degrading |

### 3. Log Analysis Tools
Tools for log pattern extraction and anomaly detection.

| Tool | Description |
|------|-------------|
| `extract_log_patterns` | Compress logs into patterns using Drain3 |
| `compare_log_patterns` | Compare patterns between time periods |
| `analyze_log_anomalies` | Find new error patterns |

### 4. Metrics Analysis Tools
Tools for time-series analysis and anomaly detection.

| Tool | Description |
|------|-------------|
| `list_time_series` | Query metrics via Cloud Monitoring API |
| `query_promql` | Execute PromQL queries |
| `detect_metric_anomalies` | Identify sudden spikes or drops |
| `compare_metric_windows` | Compare metric distributions |

### 5. Cross-Signal Correlation Tools
Tools for correlating data across traces, logs, and metrics.

| Tool | Description |
|------|-------------|
| `correlate_trace_with_metrics` | Overlay trace times on metric charts |
| `correlate_metrics_with_traces_via_exemplars` | Find traces for metric spikes |
| `build_cross_signal_timeline` | Unified timeline of all signals |

### 6. Critical Path & Dependency Tools
Tools for analyzing service dependencies and bottlenecks.

| Tool | Description |
|------|-------------|
| `analyze_critical_path` | Identify the latency-determining chain |
| `find_bottleneck_services` | Find services causing delays |
| `build_service_dependency_graph` | Map service relationships |

### 7. SLO/SLI Tools
Tools for Service Level Objective analysis.

| Tool | Description |
|------|-------------|
| `list_slos` | List defined SLOs |
| `get_slo_status` | Get current compliance status |
| `analyze_error_budget_burn` | Calculate burn rate |
| `get_golden_signals` | Get the 4 SRE golden signals |

### 8. GKE/Kubernetes Tools
Tools for Kubernetes cluster and workload analysis.

| Tool | Description |
|------|-------------|
| `get_gke_cluster_health` | Cluster health overview |
| `analyze_node_conditions` | Check for resource pressure |
| `get_pod_restart_events` | Find pod crash loops |
| `get_container_oom_events` | Find OOMKilled containers |

### 9. Remediation Tools
Tools for generating fix recommendations.

| Tool | Description |
|------|-------------|
| `generate_remediation_suggestions` | Smart fix recommendations |
| `get_gcloud_commands` | Ready-to-run gcloud commands |
| `estimate_remediation_risk` | Risk assessment |

## Creating New Tools

### Using the @adk_tool Decorator

All tools should use the `@adk_tool` decorator from `tools.common.decorators`:

```python
from sre_agent.tools.common import adk_tool

@adk_tool
async def my_new_tool(
    param1: str,
    param2: int = 10,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Tool description for the LLM.

    Args:
        param1: Description of param1.
        param2: Description of param2 (default: 10).
        project_id: GCP project ID (optional, uses env if not provided).

    Returns:
        A dictionary containing the analysis results.
    """
    # Implementation
    pass
```

### Tool Guidelines

1. **Docstrings**: Include detailed docstrings as they are shown to the LLM.
2. **Type hints**: Use proper type hints for all parameters and return values.
3. **Error handling**: Return structured error responses rather than raising exceptions.
4. **Project ID**: Accept optional `project_id` and fall back to environment variable.
5. **Async**: Prefer async functions for I/O-bound operations.

## Configuration

Tools can be enabled/disabled via the `ToolConfigManager`. See `config.py` for details.

```python
from sre_agent.tools.config import get_tool_config_manager

manager = get_tool_config_manager()
enabled_tools = manager.get_enabled_tools()
```

## Testing

Runtime connectivity checks are in `test_functions.py`. To test a tool's connectivity:

```python
from sre_agent.tools.test_functions import check_fetch_trace

result = await check_fetch_trace()
print(result.status, result.message)
```
