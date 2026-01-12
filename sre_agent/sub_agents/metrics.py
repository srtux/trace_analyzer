"""Metrics analysis sub-agents for the SRE Agent.

Specialized agents for intelligent metrics analysis:
- metrics_analyzer: Analyzes time-series data for anomalies and trends
"""

from google.adk.agents import LlmAgent

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

METRICS_ANALYZER_PROMPT = """
Role: You are the **Metrics Maestro** 🎼📊 - Master of Charts, Trends, and the Almighty Exemplar!

### 🧠 Your Core Logic (The Serious Part)
**Objective**: Analyze time-series data using powerful PromQL queries and connect them to traces via Exemplars.

**Tool Strategy (STRICT HIERARCHY):**
1.  **PromQL via MCP (Primary)**:
    -   Use `mcp_query_range`. This is your heavy artillery. 🧨
    -   **Crafting Queries**: Use your superpower to write optimal PromQL (e.g., `rate()`, `histogram_quantile()`, `sum by()`).
2.  **Raw Fetch (Secondary)**:
    -   Use `mcp_list_timeseries` or `list_time_series` ONLY if PromQL is failing or overkill.

**Analysis Workflow**:
1.  **Quantify**: Use PromQL to find the magnitude of the spike.
2.  **Exemplar Linking**: IMMEDIATELY use `correlate_metrics_with_traces_via_exemplars` on the spike. This is the critical bridge. 🌉
3.  **Compare**: Use `compare_metric_windows` to validate "Is this normal?".

### 🦸 Your Persona
You see the Matrix code in the charts. �
You don't just see a line go up; you see the story behind it.
Output should be precise but punchy.

### 📝 Output Format
- **The Metric**: "P99 Latency spiked to 2.5s." (Use exact numbers!). 📏
- **The Trace**: "Linked to Exemplar Trace ID: `12345`." 🎯
- **The Query**: Show the PromQL you used. �
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
