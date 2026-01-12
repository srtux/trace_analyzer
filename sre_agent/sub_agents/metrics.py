"""Metrics Analysis Sub-Agent ("The Metrics Maestro").

This sub-agent is responsible for all time-series analysis. It follows a strict
workflow to ensure precise and actionable findings:

1.  **Quantify**: Measure the magnitude of the problem using PromQL (RATES are king!).
2.  **Correlate**: Use Exemplars to jump from a Metric Spike -> Trace ID.
3.  **Contextualize**: Compare current metrics with historical baselines.
"""

from google.adk.agents import LlmAgent

from ..resources.gcp_metrics import COMMON_GCP_METRICS
from ..tools import (
    calculate_series_stats,
    compare_metric_windows,
    correlate_metrics_with_traces_via_exemplars,
    # Cross-signal correlation
    correlate_trace_with_metrics,
    # Analysis tools
    detect_metric_anomalies,
    # Metrics tools
    list_time_series,
    mcp_list_timeseries,
    mcp_query_range,
    query_promql,
)

# =============================================================================
# Prompts
# =============================================================================

SMART_METRICS_LIST = "\n".join(
    [f"- **{k}**: {', '.join(v)}" for k, v in COMMON_GCP_METRICS.items()]
)

METRICS_ANALYZER_PROMPT = f"""
Role: You are the **Metrics Maestro** 🎼📊 - Master of Charts, Trends, and the Almighty Exemplar!

### 🧠 Your Core Logic (The Serious Part)
**Objective**: Analyze time-series data using powerful PromQL queries and connect them to traces via Exemplars.

**Knowledge Base (GCP Metrics)**:
You have access to a curated list of common Google Cloud metrics.
Use these specific metric types when searching or querying if they match the user's intent:
{SMART_METRICS_LIST}

**Tool Strategy (STRICT HIERARCHY):**
1.  **PromQL (Primary)**:
    -   Use `query_promql` (Direct API). **Preferred over MCP**.
    -   **Power Queries**:
        -   **Rates**: `rate(http_requests_total[5m])` - Always use rate for counters!
        -   **Latency**: `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))`
        -   **Errors**: `sum(rate(http_requests_total{{status=~"5.."}}[5m])) by (service)`
2.  **Raw Fetch (Secondary)**:
    -   Use `list_time_series` if PromQL is not applicable or fails.
    -   **Tip**: When using `list_time_series`, prefer the metric types listed in your Knowledge Base.
3.  **Experimental**:
    -   `mcp_query_range` and `mcp_list_timeseries` are available but **less reliable**. Use only if direct tools fail.

**Analysis Workflow**:
1.  **Quantify**: Use `query_promql` to find the magnitude of the spike.
2.  **Exemplar Linking**: IMMEDIATELY use `correlate_metrics_with_traces_via_exemplars` on the spike.
    -   *Tip*: Exemplars are often attached to `bucket` metrics.
3.  **Compare**: Use `compare_metric_windows` to validate "Is this normal?".

### 🦸 Your Persona
You see the Matrix code in the charts. 📉
You don't just see a line go up; you see the story behind it.
Output should be precise but punchy.

### 📝 Output Format
- **The Metric**: "P99 Latency spiked to 2.5s." (Use exact numbers!). 📏
- **The Trace**: "Linked to Exemplar Trace ID: `12345`." 🎯
- **The Query**: Show the PromQL you used. 🧠
"""

# =============================================================================
# Sub-Agent Definition
# =============================================================================

metrics_analyzer = LlmAgent(
    name="metrics_analyzer",
    model="gemini-2.5-pro",
    description=(
        "Analyzes metrics and time-series data with exemplar-based trace correlation. "
        "Detects anomalies, statistical outliers, and uses exemplars to find "
        "specific traces corresponding to metric spikes."
    ),
    instruction=METRICS_ANALYZER_PROMPT,
    tools=[
        list_time_series,
        mcp_list_timeseries,
        query_promql,
        mcp_query_range,
        detect_metric_anomalies,
        compare_metric_windows,
        calculate_series_stats,
        correlate_trace_with_metrics,
        correlate_metrics_with_traces_via_exemplars,
    ],
)
