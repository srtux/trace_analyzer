# SRE Agent Architecture & Usage Guide

## Overview

The Trace Analyzer Agent is an AI-powered SRE assistant designed to help debug production issues by analyzing distributed traces, logs, and metrics from Google Cloud. It uses a hierarchical multi-agent architecture with specialized sub-agents for different analysis tasks.

## Architecture

### Two-Stage Analysis Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    Root Agent (Orchestrator)                     │
│                     "The Lead Detective"                         │
└────────────────────┬────────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
┌──────────────────┐      ┌──────────────────┐
│  Stage 1: Triage │      │ Stage 2: Deep    │
│  (Fast Detection)│      │ Dive (Root Cause)│
└──────────────────┘      └──────────────────┘
        │                         │
        ▼                         ▼
┌─────────────────────────────────────────────┐
│ Parallel Sub-Agents                         │
├─────────────────────────────────────────────┤
│ Stage 1:                                    │
│  • Latency Analyzer   (timing comparison)   │
│  • Error Analyzer     (error detection)     │
│  • Structure Analyzer (topology changes)    │
│  • Statistics Analyzer(percentiles,anomaly) │
│                                             │
│ Stage 2:                                    │
│  • Causality Analyzer (root cause ranking) │
│  • Service Impact     (blast radius)       │
└─────────────────────────────────────────────┘
```

## Tool Categories

### 1. Core Investigation Tools

#### `run_two_stage_analysis(baseline_trace_id, target_trace_id, project_id)`
**Purpose**: Orchestrates the complete two-stage investigation.

**When to use**:
- You have identified two traces to compare (baseline vs anomalous)
- You want comprehensive analysis with root cause identification
- You need both quick triage and deep dive insights

**Returns**: Combined report from all 6 sub-agents

**Example**:
```python
result = run_two_stage_analysis(
    baseline_trace_id="abc123...",  # P50 trace
    target_trace_id="def456...",     # P95 or error trace
    project_id="my-project"
)
```

---

### 2. Trace Discovery & Retrieval

#### `find_example_traces(project_id, filter_string, time_window_minutes)`
**Purpose**: Intelligently discovers baseline and anomalous traces.

**Algorithm**:
- Fetches traces matching the filter
- Calculates composite anomaly scores based on:
  - Latency (Z-score deviation)
  - Error presence
  - Span count anomalies
- Returns P50 trace (baseline) and P95+ trace (anomalous)

**When to use**:
- Starting an investigation without specific trace IDs
- Need representative baseline and problematic traces
- Want automated anomaly detection

**Example**:
```python
traces = find_example_traces(
    project_id="my-project",
    filter_string="span:my-service-endpoint",
    time_window_minutes=60
)
# Returns: {"baseline": {...}, "target": {...}}
```

#### `list_traces(project_id, filter_string, limit, min_latency_ms, max_latency_ms)`
**Purpose**: Searches for traces with advanced filtering.

**Filters**:
- `filter_string`: Cloud Trace filter syntax (span names, attributes)
- Time windows
- Latency ranges
- Error status

**When to use**:
- Need multiple traces for pattern analysis
- Building baselines from many samples
- Exploring trace distribution

**Example**:
```python
# Find all slow traces with errors in the last hour
traces = list_traces(
    project_id="my-project",
    filter_string="span:database-query",
    min_latency_ms=1000,  # > 1 second
    limit=50
)
```

#### `fetch_trace(project_id, trace_id)`
**Purpose**: Retrieves a specific trace with caching.

**Features**:
- Thread-safe TTL cache (5 min default)
- Prevents redundant API calls
- Returns normalized JSON structure

**When to use**:
- Have specific trace ID from logs/alerts
- Need detailed span information
- Building custom analysis

#### `summarize_trace(trace_data)`
**Purpose**: Creates compact trace summaries to save context tokens.

**Returns**:
- Top 5 slowest spans
- Error count and samples
- Total span count
- Duration

**When to use**:
- Context window is filling up
- Need overview before deep analysis
- Presenting trace info to user

---

### 3. Data Quality & Validation

#### `validate_trace_quality(trace_json)`
**Purpose**: Checks trace data quality and detects issues.

**Validations**:
- **Orphaned spans**: Spans with missing parents
- **Negative durations**: Invalid time calculations
- **Clock skew**: Child spans outside parent timespan
- **Timestamp errors**: Parsing failures

**Returns**: `{"valid": bool, "issue_count": int, "issues": [...]}`

**When to use**:
- Trace analysis produces unexpected results
- Investigating data collection issues
- Before running expensive analysis
- Debugging instrumentation problems

**Example**:
```python
quality = validate_trace_quality(trace_json)
if not quality["valid"]:
    print(f"Warning: {quality['issue_count']} data quality issues found")
    # Handle clock skew, orphaned spans, etc.
```

---

### 4. Pattern Analysis

#### `analyze_trace_patterns(traces, lookback_window_minutes=60)`
**Purpose**: Detects patterns across multiple traces.

**Patterns Detected**:
1. **Recurring Slowdowns**: Consistently slow spans (low variance)
   - Criteria: mean > 100ms, CV < 0.3
   - Indicates: Structural performance issues

2. **Intermittent Issues**: High variance spans
   - Criteria: CV > 0.5, mean > 50ms
   - Indicates: Flaky behavior, resource contention

3. **High Variance**: Unpredictable performance
   - Criteria: CV > 0.7
   - Indicates: Load-dependent issues

4. **Trends**: Degradation/improvement over time
   - Compares first half vs second half
   - Detects: >15% change

**When to use**:
- Investigating intermittent issues
- Detecting performance degradation
- Need more than 3 traces (minimum)
- Building long-term baselines

**Example**:
```python
# Analyze 20 traces from the last hour
traces = list_traces(..., limit=20)
patterns = analyze_trace_patterns(traces, lookback_window_minutes=60)

# Results:
# patterns["patterns"]["recurring_slowdowns"] → Always slow
# patterns["patterns"]["intermittent_issues"] → Sometimes slow
# patterns["overall_trend"] → "degrading" | "improving" | "stable"
```

---

### 5. Correlation & Context

#### `list_log_entries(project_id, filter_str, limit=10)`
**Purpose**: Retrieves correlated logs from Cloud Logging.

**Filter Examples**:
```python
# Logs for a specific trace
filter_str = 'trace="projects/my-project/traces/abc123..."'

# Errors in a service
filter_str = 'resource.type="k8s_container" AND severity>=ERROR'

# Logs with specific field
filter_str = 'jsonPayload.user_id="12345"'
```

**When to use**:
- Need context beyond spans (user actions, errors)
- Correlating trace with application logs
- Finding error messages or stack traces

#### `get_logs_for_trace(project_id, trace_id)`
**Purpose**: Convenience wrapper to get logs for a trace.

**Returns**: Logs with matching trace ID.

#### `list_time_series(project_id, filter_str, minutes_ago=60)`
**Purpose**: Queries metrics from Cloud Monitoring.

**Use Cases**:
- CPU/memory usage during slow periods
- Request rates and error rates
- Custom application metrics
- Infrastructure metrics

**Example**:
```python
# Get CPU usage for a service
metrics = list_time_series(
    project_id="my-project",
    filter_str='metric.type="compute.googleapis.com/instance/cpu/utilization"',
    minutes_ago=30
)
```

#### `list_error_events(project_id, service_name, time_range_hours=24)`
**Purpose**: Retrieves errors from Error Reporting.

**When to use**:
- Finding error spikes
- Correlating errors with traces
- Understanding error distribution

---

### 6. BigQuery Tools (Large-Scale Analysis)

#### Why Use BigQuery?

**Use BigQuery when**:
- ✅ Analyzing **> 50-100 traces** (API limits)
- ✅ Historical data **> 7 days**
- ✅ Complex aggregations (percentiles, GROUP BY)
- ✅ Joining traces with logs
- ✅ Building statistical baselines

**Don't use BigQuery when**:
- ❌ Need real-time/recent data (< 5 min delay in exports)
- ❌ Analyzing 1-10 traces (use Trace API)
- ❌ Simple trace retrieval

#### `execute_sql(projectId, query)`
**Purpose**: Run SQL queries against BigQuery datasets.

**Common Queries**:

**1. Trace Analysis - P95 Latency Over Time**:
```sql
SELECT
  DATE(timestamp) as date,
  APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(95)] as p95_latency
FROM `project.dataset.traces`
WHERE span_name = 'my-operation'
GROUP BY date
ORDER BY date
```

**2. Log Analysis - Error Pattern Detection**:
```sql
SELECT
  JSON_EXTRACT_SCALAR(json_payload, '$.error_type') as error_type,
  COUNT(*) as error_count,
  ARRAY_AGG(DISTINCT trace_id LIMIT 5) as sample_traces
FROM `project.dataset.logs`
WHERE severity = 'ERROR'
  AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
GROUP BY error_type
ORDER BY error_count DESC
LIMIT 10
```

**3. Combined Analysis - Traces with High Error Rate**:
```sql
WITH trace_errors AS (
  SELECT
    trace_id,
    COUNT(*) as error_count
  FROM `project.dataset.logs`
  WHERE severity = 'ERROR'
  GROUP BY trace_id
)
SELECT
  t.trace_id,
  t.duration_ms,
  e.error_count
FROM `project.dataset.traces` t
JOIN trace_errors e ON t.trace_id = e.trace_id
WHERE e.error_count > 5
ORDER BY t.duration_ms DESC
LIMIT 20
```

**4. N+1 Query Detection at Scale**:
```sql
SELECT
  trace_id,
  span_name,
  COUNT(*) as repetitions,
  SUM(span_duration_ms) as total_duration
FROM `project.dataset.traces`
WHERE span_name LIKE '%query%'
GROUP BY trace_id, span_name
HAVING COUNT(*) > 10  -- More than 10 repetitions
ORDER BY total_duration DESC
```

**5. Span Performance Trends**:
```sql
SELECT
  DATE_TRUNC(timestamp, HOUR) as hour,
  span_name,
  APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(50)] as p50,
  APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(95)] as p95,
  APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(99)] as p99,
  COUNT(*) as sample_count
FROM `project.dataset.traces`
WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY hour, span_name
ORDER BY hour DESC, span_name
```

#### `list_dataset_ids(projectId)`, `list_table_ids(projectId, datasetId)`, `get_table_info(projectId, datasetId, tableId)`
**Purpose**: Explore available BigQuery datasets and tables.

**Workflow**:
1. `list_dataset_ids` → Find available datasets
2. `list_table_ids` → Find tables in dataset
3. `get_table_info` → Get schema and row count
4. `execute_sql` → Query the data

---

## Anti-Pattern Detection

The agent automatically detects these performance anti-patterns:

### 1. N+1 Queries
**Detection Algorithm**:
- Finds 3+ consecutive spans with identical names
- Total duration > 50ms
- Sequential (not parallel)

**Severity**:
- High: > 200ms total
- Medium: > 50ms total

**Example Finding**:
```json
{
  "type": "n_plus_one",
  "span_name": "database.query.user",
  "count": 15,
  "total_duration_ms": 450,
  "impact": "high"
}
```

### 2. Serial Chains
**Detection Algorithm**:
- Finds operations running sequentially (gap < 10ms)
- NOT parent-child (that's expected)
- 3+ operations in chain
- Total duration > 100ms

**Severity**:
- High: > 500ms total
- Medium: > 100ms total

**Recommendation**: Parallelize with async/await

**Example Finding**:
```json
{
  "type": "serial_chain",
  "span_names": ["api.fetch_user", "api.fetch_orders", "api.fetch_reviews"],
  "count": 3,
  "total_duration_ms": 650,
  "impact": "high",
  "recommendation": "Consider parallelizing these operations..."
}
```

---

## Critical Path Analysis

### Enhanced Algorithm (v2)

The critical path algorithm now handles async/concurrent operations:

**Algorithm**:
1. Calculate **self-time** for each span (time not overlapping with children)
2. Use dynamic programming to find longest **blocking path**
3. Account for concurrent children (merge overlapping intervals)
4. Discount non-blocking children (finish early, don't block parent)

**Output**:
```json
{
  "critical_path": [
    {
      "name": "http.request",
      "span_id": "abc123",
      "duration_ms": 500,
      "self_time_ms": 50,
      "contribution_pct": 10,
      "blocking_contribution_pct": 15
    },
    ...
  ],
  "total_critical_duration_ms": 350,
  "trace_duration_ms": 500,
  "parallelism_ratio": 1.43,
  "parallelism_pct": 30
}
```

**Key Metrics**:
- **self_time_ms**: Actual work (not child overhead)
- **parallelism_ratio**: Total time / Critical time
- **parallelism_pct**: How much parallelism is achieved

**Interpretation**:
- `parallelism_ratio` = 1.0 → Fully sequential (no parallelism)
- `parallelism_ratio` = 2.0 → 50% parallel execution
- `parallelism_ratio` = 4.0 → 75% parallel execution

---

## Root Cause Analysis

### Span-ID Level Precision

The causal analysis now uses actual span IDs (not name approximations):

**Multi-Factor Confidence Scoring**:
1. **Absolute time difference**: Higher diff = more impact
2. **Critical path membership**: 2x multiplier if on critical path
3. **Self-time contribution**: 1.3x boost if >30% of diff is self-time
4. **Call hierarchy depth**: Up to 1.5x boost for deeper spans

**Formula**:
```
score = diff_ms × depth_factor × critical_path_multiplier × self_time_multiplier

Where:
  depth_factor = min(1.0 + (depth × 0.1), 1.5)
  critical_path_multiplier = 2.0 if on critical path else 1.0
  self_time_multiplier = 1.3 if (self_time > diff_ms × 0.3) else 1.0
```

**Output**:
```json
{
  "root_cause_candidates": [
    {
      "span_id": "xyz789",
      "span_name": "database.query",
      "diff_ms": 250,
      "diff_percent": 400,
      "on_critical_path": true,
      "self_time_ms": 200,
      "depth": 3,
      "confidence_score": 975,
      "is_likely_root_cause": true
    }
  ],
  "analysis_method": "span_id_level_critical_path_analysis"
}
```

---

## Best Practices

### Investigation Workflow

**1. Quick Triage (< 2 minutes)**:
```python
# Find problematic traces
traces = find_example_traces(project_id, filter_string="span:my-service")

# Quick validation
validate_trace_quality(traces["target"])

# Run two-stage analysis
result = run_two_stage_analysis(
    baseline_trace_id=traces["baseline"]["trace_id"],
    target_trace_id=traces["target"]["trace_id"],
    project_id=project_id
)
```

**2. Deep Investigation (5-10 minutes)**:
```python
# Get more context
logs = get_logs_for_trace(project_id, target_trace_id)
metrics = list_time_series(project_id, filter_str='...', minutes_ago=30)

# Pattern analysis
recent_traces = list_traces(project_id, filter_string="...", limit=20)
patterns = analyze_trace_patterns(recent_traces)
```

**3. Historical Analysis (BigQuery)**:
```sql
-- Build baseline from last 30 days
SELECT
  span_name,
  APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(50)] as baseline_p50,
  APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(95)] as baseline_p95
FROM `project.dataset.traces`
WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY span_name
```

### Performance Tips

**Minimize API Calls**:
- Use `find_example_traces` instead of multiple `list_traces` calls
- Use `summarize_trace` to reduce context usage
- Leverage trace cache (5 min TTL)

**Use BigQuery for Scale**:
- Switch to BigQuery when analyzing > 50 traces
- Pre-aggregate in BigQuery, analyze results with tools
- Join traces with logs for comprehensive view

**Parallel Analysis**:
- Use `analyze_trace_patterns` for multi-trace insights
- Let the two-stage pipeline handle parallelism automatically

---

## Common Scenarios

### Scenario 1: "My endpoint is slow"
```python
1. find_example_traces(filter_string="span:my-endpoint")
2. run_two_stage_analysis(baseline, target)
3. Check for N+1 queries, serial chains in report
4. If needed: get_logs_for_trace for application context
```

### Scenario 2: "Intermittent timeouts"
```python
1. list_traces(filter_string="...", limit=50)
2. analyze_trace_patterns(traces) → Look for high variance spans
3. Run analysis on min/max traces from pattern results
4. Check metrics: list_time_series for infrastructure correlation
```

### Scenario 3: "Performance regression after deploy"
```python
1. Define time windows: before_deploy, after_deploy
2. Use BigQuery to compare P95 before/after
3. find_example_traces from each window
4. run_two_stage_analysis to identify what changed
5. Check structure_analyzer for new spans or topology changes
```

### Scenario 4: "Database queries are slow"
```python
1. list_traces(filter_string="span:database")
2. Check for N+1 queries in results
3. Use BigQuery to find patterns:
   - COUNT(*) GROUP BY query_pattern
   - Identify most frequent slow queries
4. Correlate with logs for query parameters
```

---

## Troubleshooting

### "No traces found"
- Check project ID
- Verify trace export is enabled
- Expand time window
- Check filter syntax

### "Data quality issues"
- Run `validate_trace_quality`
- Check for clock skew (distributed systems)
- Verify instrumentation configuration

### "BigQuery not working"
- Verify export sink is configured
- Check dataset and table names
- Ensure exports are recent (5+ min delay)
- Verify permissions

### "Analysis takes too long"
- Use `summarize_trace` first
- Reduce number of traces
- Use BigQuery for pre-aggregation
- Check for large traces (>1000 spans)

---

## Metrics & Observability

The agent itself is instrumented with OpenTelemetry:

**Metrics Emitted**:
- `trace_analyzer.tool.execution_duration`: Histogram of tool call durations
- `trace_analyzer.tool.execution_count`: Counter of tool invocations
- `trace_analyzer.analysis.anomalies_detected`: Counter of anomalies found

**Spans Created**:
- Each tool call creates a span with attributes
- Exceptions are recorded with `span.record_exception()`
- Success/failure tracked in metrics

---

## Advanced: Custom Analysis

### Building Custom Workflows

The agent's tools are composable. Example custom workflow:

```python
# Custom: Find all traces with specific error pattern
def find_traces_with_error_pattern(project_id, error_type, hours=24):
    # 1. Query BigQuery for error traces
    query = f"""
    SELECT DISTINCT trace_id
    FROM `project.logs`
    WHERE severity = 'ERROR'
      AND json_payload.error_type = '{error_type}'
      AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours} HOUR)
    LIMIT 100
    """
    trace_ids = execute_sql(project_id, query)

    # 2. Fetch and analyze each trace
    results = []
    for trace_id in trace_ids:
        trace = fetch_trace(project_id, trace_id)
        quality = validate_trace_quality(trace)
        if quality["valid"]:
            results.append(trace)

    # 3. Pattern analysis
    patterns = analyze_trace_patterns(results)
    return patterns
```

---

## Summary

This agent provides:
- ✅ Automated trace comparison and diff analysis
- ✅ Anti-pattern detection (N+1, serial chains)
- ✅ Root cause analysis with confidence scoring
- ✅ Multi-trace pattern detection
- ✅ BigQuery integration for scale
- ✅ Log/metric correlation
- ✅ Data quality validation

**Key Strengths**:
- Handles async/concurrent architectures
- Span-ID level precision (no approximations)
- Multi-factor root cause scoring
- Extensible via BigQuery
- Production-ready observability
