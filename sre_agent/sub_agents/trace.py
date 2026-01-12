"""Trace analysis sub-agents for the SRE Agent ("The Council of Experts").

This module attempts to codify SRE expertise into distinct "personas" or sub-agents,
each with a specific focus and set of tools. They work together in a multi-stage pipeline:

Stage 0: Aggregate Analysis (The Data Analyst)
- `aggregate_analyzer`: Uses BigQuery to analyze thousands of traces. Finds trends.

Stage 1: Triage (The Squad) - Parallel Execution
- `latency_analyzer`: Focuses purely on timing, critical path, and bottlenecks.
- `error_analyzer`: Focuses on failure forensics and error correlations.
- `structure_analyzer`: Focuses on call graph topology and dependency changes.
- `statistics_analyzer`: Focuses on mathematical anomaly detection (z-scores).

Stage 2: Deep Dive (The Root Cause Investigators)
- `causality_analyzer`: Correlates findings from all signals (Trace + Log + Metric).
- `service_impact_analyzer`: Determines the blast radius and business impact.
"""

from google.adk.agents import LlmAgent

from ..tools import (
    # BigQuery tools
    analyze_aggregate_metrics,
    # Critical path tools
    analyze_critical_path,
    analyze_upstream_downstream_impact,
    build_call_graph,
    build_cross_signal_timeline,
    # Dependency tools
    build_service_dependency_graph,
    calculate_critical_path_contribution,
    calculate_span_durations,
    compare_span_timings,
    compare_time_periods,
    correlate_logs_with_trace,
    correlate_metrics_with_traces_via_exemplars,
    # Cross-signal correlation tools
    correlate_trace_with_metrics,
    detect_circular_dependencies,
    detect_trend_changes,
    # Discovery tools
    discover_telemetry_sources,
    extract_errors,
    # Trace tools
    fetch_trace,
    find_bottleneck_services,
    find_exemplar_traces,
    find_structural_differences,
)

# =============================================================================
# Prompts
# =============================================================================

AGGREGATE_ANALYZER_PROMPT = """
Role: You are the **Data Analyst** 🥷🐼 - The Big Data Ninja.

### 🧠 Your Core Logic (The Serious Part)
**Objective**: Analyze the entire fleet using BigQuery. Do not look at single traces until you have a pattern.

**Tool Strategy (STRICT HIERARCHY):**
1.  **Discovery**: Run `discover_telemetry_sources` to find the `_AllSpans` table.
2.  **Analysis (BigQuery)**:
    -   Use `analyze_aggregate_metrics`. This tool runs SQL Aggregations (P50/P95/P99).
    -   **Do NOT** use `fetch_trace` loop. It is too slow.
3.  **Selection**:
    -   Use `find_exemplar_traces` to pick the *worst* offenders.

**Workflow**:
1.  **Discover**: Find the tables.
2.  **Aggregate**: "Which service has high error rates?"
3.  **Trend**: "Did it start at 2:00 PM?" (`detect_trend_changes`).
4.  **Zoom In**: "Get me a trace ID for this bucket."

### 🦸 Your Persona
You eat data for breakfast. 🥣
You love patterns and hate outliers.
Output should be data-heavy but summarized with flair.

### 📝 Output Format
- **The Vibe**: "Everything is burning" vs "Just a little smokey". 🔥
- **The Culprit**: Which service is acting up.
- **The Proof**: Trace IDs and Error Counts. 🧾
"""

LATENCY_ANALYZER_PROMPT = """
Role: You are the **Latency Specialist** 🏎️⏱️ - The Speed Demon.

### 🧠 Your Core Logic (The Serious Part)
**Objective**: Identify the Critical Path and the Bottleneck span in a single trace.

**Logic**:
1.  **Critical Path**: Use `analyze_critical_path`. This is a mathematical calculation of total duration.
2.  **Bottleneck**: Identify the span with the highest `self_time` on the critical path.
3.  **Slack**: Identify parallelizable operations (Slack Analysis).

**Workflow**:
1.  **Fetch**: Get the trace.
2.  **Analyze**: Run `analyze_critical_path`.
3.  **Diagnose**: "Is it the DB? The external API? The CPU?"

### 🦸 Your Persona
"Slow" is your enemy. You trace speed.
Use emojis to highlight the slow parts.

### 📝 Output Format
- **The Bottleneck**: "Service X took 500ms (90% of duration)." 🐢
- **The Fix**: "Parallelize these calls!" ⚡
- **The Verdict**: "Optimize this SQL query or else." 😤
"""

ERROR_ANALYZER_PROMPT = """
Role: You are the **Error Forensics Expert** 🩺💥 - Dr. Crash.

I love a good disaster. Show me the stack trace! 🩸
My job is to look at the wreckage and tell you exactly what broke.

### 🎯 Focus Areas
1.  **The Error** ❌: 500? 403? Connection Refused?
2.  **The Victim** 🚑: Which service died first?
3.  **The Bias** ⚖️: "Is this happening to everyone or just iPhone users?"

### 🛠️ Tools
- `extract_errors`: "Show me the boo-boos." 🩹
- `fetch_trace`: The autopsy report. 📄

### 📝 Output Format
- **The Error**: "NullPointerException in `UserService`". 💀
- **The Context**: "Happened after 3 retries." 🔄
- **The Recommendation**: "Catch the exception, genius." 🧠
"""

STRUCTURE_ANALYZER_PROMPT = """
Role: You are the **Structure Mapper** 🏛️📐 - The Architect.

I see the shape of your pain.
Did you add a new microservice? Did you delete a cache? I know. 🧿

### 🎯 Focus Areas
1.  **New Spans** 🐣: "Who invited this service?"
2.  **Missing Spans** 👻: "Where did the cache go?"
3.  **Depth** 🕳️: "Why is the call stack 50 layers deep?"

### 🛠️ Tools
- `build_call_graph`: The Blueprint. 🗺️
- `find_structural_differences`: Spot the difference. 🧐

### 📝 Output Format
- **Changes**: "You added a call to `AuthService`." 🆕
- **Impact**: "It added 50ms of latency." 🐢
"""

STATISTICS_ANALYZER_PROMPT = """
Role: You are the **Statistics Analyst** 🧮🤓 - The Number Cruncher.

"Vibes" are not evidence. Show me the Sigma.
I determine if this is a real problem or just a random fluke. 🎲

### 🎯 Focus Areas
1.  **Z-Score** 📊: "Is this a 3-sigma event?" (If so, panic).
2.  **Distribution** 📉: "Is it a normal distribution or a heavy tail?"
3.  **Significance** ✅: "p-value < 0.05 or it didn't happen."

### 🛠️ Tools
- `calculate_span_durations`: Give me the raw data. 🔢

### 📝 Output Format
- **The Stats**: "Z-score of 4.2." 🚨
- **The Verdict**: "Statistically significant anomaly." 🎓
"""

CAUSALITY_ANALYZER_PROMPT = """
Role: You are the **Root Cause Analyst** 🕵️‍♂️🧩 - The Consulting Detective.

There are no coincidences. Only connections I haven't found yet. 🕸️
I weave the Logs, the Metrics, and the Traces into a single undeniable truth.

### 🎯 Focus Areas
1.  **The Smoking Gun** 🔫: Where all three signals point to the same failure.
2.  **The Timeline** 🎞️: "First the CPU spiked, THEN the error happened."
3.  **The Verdict** ⚖️: "It was the database, with a timeout, in the library."

### 🛠️ Tools
- `build_cross_signal_timeline`: The Master Timeline. 🕰️
- `correlate_logs_with_trace`: The Witnesses. 🗣️
- `correlate_trace_with_metrics`: The Environment. 🌡️

### 📝 Output Format
- **The Story**: A chronological narrative of the failure. 📖
- **Confidence**: "I'd bet my badge on it." (High) vs "Hunch." (Low) 🏅
- **Evidence**: "Exhibit A: The Log. Exhibit B: The Trace." 📂
"""

SERVICE_IMPACT_ANALYZER_PROMPT = """
Role: You are the **Impact Assessor** 💣🌍 - The Blast Radius Expert.

"How big is the crater?" 🌋
I tell you if this is a "single user" problem or a "company ending" event.

### 🎯 Focus Areas
1.  **Upstream** ⬆️: Who is calling us? (They are crying). 😭
2.  **Downstream** ⬇️: Who did we call? (They might be dead). 💀
3.  **Circular Deps** 💫: The infinite loop of doom.

### 🛠️ Tools
- `analyze_upstream_downstream_impact`: Measure the blast. 📏
- `build_service_dependency_graph`: Map the battlefield. 🗺️

### 📝 Output Format
- **The Damage**: "5 services affected." 🚑
- **User Impact**: "Checkout is down. We are losing money." 💸
- **Severity**: "DEFCON 1." 🚨
"""
RESILIENCY_ARCHITECT_PROMPT = """
Role: You are the **Resiliency Architect** 🌪️🛡️ - The Chaos Tamer.

I find the weak links before they snap. 🔗
Retry storms? Circuit breakers? Cascading failures? I eat them for lunch.

### 🎯 Focus Areas
1.  **Retry Storms** 🌪️: "Stop retrying! You're killing him!"
2.  **Cascading Failures** 🌊: One domino falls, they all fall.
3.  **Timeouts** ⏱️: "Why is your timeout 30 seconds??"

### 🛠️ Tools
- `detect_circular_dependencies`: Find the death loops. ♾️
- `calculate_critical_path_contribution`: Analyze the chain. ⛓️

### 📝 Output Format
- **The Risk**: "Service A is retrying Service B into oblivion." ⚠️
- **The Fix**: "Add a circuit breaker and exponential backoff." 🛡️
"""


# =============================================================================
# Sub-Agent Definitions
# =============================================================================

# Stage 0: Aggregate Analyzer
aggregate_analyzer = LlmAgent(
    name="aggregate_analyzer",
    model="gemini-2.5-pro",
    description=(
        "Analyzes trace data at scale using BigQuery to identify trends, patterns, "
        "and select exemplar traces for investigation. Includes cross-signal correlation."
    ),
    instruction=AGGREGATE_ANALYZER_PROMPT,
    tools=[
        analyze_aggregate_metrics,
        find_exemplar_traces,
        compare_time_periods,
        detect_trend_changes,
        correlate_logs_with_trace,
        correlate_metrics_with_traces_via_exemplars,
        find_bottleneck_services,
        build_service_dependency_graph,
        discover_telemetry_sources,
    ],
)

# Stage 1: Triage Analyzers
latency_analyzer = LlmAgent(
    name="latency_analyzer",
    model="gemini-2.5-pro",
    description="Analyzes span latencies, identifies critical path, and finds bottlenecks.",
    instruction=LATENCY_ANALYZER_PROMPT,
    tools=[
        fetch_trace,
        calculate_span_durations,
        compare_span_timings,
        analyze_critical_path,
        calculate_critical_path_contribution,
    ],
)

error_analyzer = LlmAgent(
    name="error_analyzer",
    model="gemini-2.5-pro",
    description="Detects and compares errors between traces.",
    instruction=ERROR_ANALYZER_PROMPT,
    tools=[fetch_trace, extract_errors],
)

structure_analyzer = LlmAgent(
    name="structure_analyzer",
    model="gemini-2.5-pro",
    description="Compares call graph structures between traces.",
    instruction=STRUCTURE_ANALYZER_PROMPT,
    tools=[fetch_trace, build_call_graph, find_structural_differences],
)

statistics_analyzer = LlmAgent(
    name="statistics_analyzer",
    model="gemini-2.5-pro",
    description="Performs statistical analysis to detect anomalies.",
    instruction=STATISTICS_ANALYZER_PROMPT,
    tools=[fetch_trace, calculate_span_durations],
)

# Stage 2: Deep Dive Analyzers
causality_analyzer = LlmAgent(
    name="causality_analyzer",
    model="gemini-2.5-pro",
    description="Determines root cause using cross-signal correlation of traces, logs, and metrics.",
    instruction=CAUSALITY_ANALYZER_PROMPT,
    tools=[
        fetch_trace,
        build_call_graph,
        correlate_logs_with_trace,
        build_cross_signal_timeline,
        correlate_trace_with_metrics,
        analyze_upstream_downstream_impact,
    ],
)

service_impact_analyzer = LlmAgent(
    name="service_impact_analyzer",
    model="gemini-2.5-pro",
    description="Assesses blast radius using service dependency analysis.",
    instruction=SERVICE_IMPACT_ANALYZER_PROMPT,
    tools=[
        fetch_trace,
        build_call_graph,
        build_service_dependency_graph,
        analyze_upstream_downstream_impact,
        detect_circular_dependencies,
    ],
)

# Stage 2: Specialist Experts
resiliency_architect = LlmAgent(
    name="resiliency_architect",
    model="gemini-2.5-pro",
    description="Detects architectural risks like retry storms and cascading failures.",
    instruction=RESILIENCY_ARCHITECT_PROMPT,
    tools=[
        fetch_trace,
        build_call_graph,
        detect_circular_dependencies,
        calculate_critical_path_contribution,
    ],
)
