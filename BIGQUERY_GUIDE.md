# BigQuery Integration Guide for Trace & Log Analysis

## Overview

BigQuery provides powerful SQL-based analysis capabilities for traces and logs at scale. This guide covers common patterns, example queries, and best practices.

## Prerequisites

### 1. Enable Export Sinks

**For Traces:**
```bash
# Export traces to BigQuery
gcloud logging sinks create trace-export \
  bigquery.googleapis.com/projects/PROJECT_ID/datasets/traces \
  --log-filter='resource.type="cloud_trace"'
```

**For Logs:**
```bash
# Export all logs
gcloud logging sinks create log-export \
  bigquery.googleapis.com/projects/PROJECT_ID/datasets/logs \
  --log-filter='*'

# Export only application logs
gcloud logging sinks create app-log-export \
  bigquery.googleapis.com/projects/PROJECT_ID/datasets/app_logs \
  --log-filter='resource.type="k8s_container" OR resource.type="cloud_run_revision"'
```

### 2. Schema Overview

**Trace Table Schema** (from Cloud Trace export):
```sql
- trace_id: STRING
- span_id: STRING
- parent_span_id: STRING
- span_name: STRING
- start_time: TIMESTAMP
- end_time: TIMESTAMP
- span_duration_ms: FLOAT64
- labels: RECORD (repeated key-value pairs)
- status: RECORD (code, message)
```

**Log Table Schema** (from Cloud Logging export):
```sql
- timestamp: TIMESTAMP
- severity: STRING
- json_payload: JSON
- text_payload: STRING
- trace: STRING (format: "projects/PROJECT/traces/TRACE_ID")
- resource: RECORD (type, labels)
- labels: RECORD
- http_request: RECORD (if available)
```

## Common Query Patterns

### 1. Performance Analysis

#### Calculate Percentiles Over Time
```sql
-- P50, P95, P99 latency by day
SELECT
  DATE(start_time) as date,
  span_name,
  APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(50)] as p50_ms,
  APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(95)] as p95_ms,
  APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(99)] as p99_ms,
  COUNT(*) as sample_count
FROM `PROJECT.DATASET.traces`
WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND span_name IS NOT NULL
GROUP BY date, span_name
ORDER BY date DESC, p95_ms DESC
LIMIT 100
```

#### Find Slowest Operations
```sql
-- Top 20 slowest spans in the last 24 hours
SELECT
  span_name,
  trace_id,
  span_duration_ms,
  ARRAY(
    SELECT label.value
    FROM UNNEST(labels) AS label
    WHERE label.key = 'http.url'
  )[SAFE_OFFSET(0)] as url,
  start_time
FROM `PROJECT.DATASET.traces`
WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
  AND span_duration_ms > 1000  -- > 1 second
ORDER BY span_duration_ms DESC
LIMIT 20
```

#### Detect Performance Regression
```sql
-- Compare this week vs last week
WITH this_week AS (
  SELECT
    span_name,
    APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(95)] as p95
  FROM `PROJECT.DATASET.traces`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  GROUP BY span_name
),
last_week AS (
  SELECT
    span_name,
    APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(95)] as p95
  FROM `PROJECT.DATASET.traces`
  WHERE start_time BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
                       AND TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  GROUP BY span_name
)
SELECT
  tw.span_name,
  tw.p95 as this_week_p95,
  lw.p95 as last_week_p95,
  tw.p95 - lw.p95 as diff_ms,
  ROUND((tw.p95 - lw.p95) / lw.p95 * 100, 1) as pct_change
FROM this_week tw
JOIN last_week lw ON tw.span_name = lw.span_name
WHERE tw.p95 > lw.p95 * 1.2  -- 20% slower
ORDER BY diff_ms DESC
LIMIT 20
```

### 2. N+1 Query Detection

#### Find Repeated Spans in Traces
```sql
-- Detect potential N+1 query patterns
WITH span_counts AS (
  SELECT
    trace_id,
    span_name,
    COUNT(*) as repetition_count,
    SUM(span_duration_ms) as total_duration_ms,
    MIN(start_time) as first_occurrence,
    MAX(end_time) as last_occurrence
  FROM `PROJECT.DATASET.traces`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
    AND (span_name LIKE '%query%' OR span_name LIKE '%database%')
  GROUP BY trace_id, span_name
)
SELECT
  span_name,
  COUNT(*) as trace_count,
  AVG(repetition_count) as avg_repetitions,
  MAX(repetition_count) as max_repetitions,
  AVG(total_duration_ms) as avg_total_duration,
  ARRAY_AGG(trace_id ORDER BY repetition_count DESC LIMIT 3) as sample_traces
FROM span_counts
WHERE repetition_count >= 10  -- Called 10+ times in a trace
GROUP BY span_name
HAVING COUNT(*) > 5  -- Affects multiple traces
ORDER BY avg_total_duration DESC
LIMIT 20
```

#### Detect Serial Execution Patterns
```sql
-- Find operations that could be parallelized
WITH sequential_spans AS (
  SELECT
    trace_id,
    span_id,
    span_name,
    start_time,
    end_time,
    span_duration_ms,
    LAG(end_time) OVER (PARTITION BY trace_id ORDER BY start_time) as prev_end_time
  FROM `PROJECT.DATASET.traces`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
)
SELECT
  trace_id,
  ARRAY_AGG(STRUCT(span_name, span_duration_ms) ORDER BY start_time) as sequential_ops,
  COUNT(*) as chain_length,
  SUM(span_duration_ms) as total_duration
FROM sequential_spans
WHERE TIMESTAMP_DIFF(start_time, prev_end_time, MILLISECOND) < 10  -- Gap < 10ms
GROUP BY trace_id
HAVING COUNT(*) >= 3  -- Chain of 3+ operations
ORDER BY total_duration DESC
LIMIT 50
```

### 3. Error Analysis

#### Error Frequency by Type
```sql
-- Count errors by type from logs
SELECT
  JSON_EXTRACT_SCALAR(json_payload, '$.error.type') as error_type,
  JSON_EXTRACT_SCALAR(json_payload, '$.error.message') as error_message,
  COUNT(*) as error_count,
  COUNT(DISTINCT REGEXP_EXTRACT(trace, r'traces/(.+)')) as affected_traces,
  MIN(timestamp) as first_seen,
  MAX(timestamp) as last_seen,
  ARRAY_AGG(DISTINCT REGEXP_EXTRACT(trace, r'traces/(.+)') LIMIT 5) as sample_traces
FROM `PROJECT.DATASET.logs`
WHERE severity = 'ERROR'
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
  AND json_payload IS NOT NULL
GROUP BY error_type, error_message
ORDER BY error_count DESC
LIMIT 20
```

#### Correlate Errors with Slow Traces
```sql
-- Find traces that have both errors and high latency
WITH trace_errors AS (
  SELECT
    REGEXP_EXTRACT(trace, r'traces/(.+)') as trace_id,
    COUNT(*) as error_count,
    ARRAY_AGG(JSON_EXTRACT_SCALAR(json_payload, '$.error.message') LIMIT 3) as error_messages
  FROM `PROJECT.DATASET.logs`
  WHERE severity = 'ERROR'
    AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
  GROUP BY trace_id
),
trace_perf AS (
  SELECT
    trace_id,
    MAX(end_time) - MIN(start_time) as total_duration_seconds,
    COUNT(*) as span_count
  FROM `PROJECT.DATASET.traces`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
  GROUP BY trace_id
)
SELECT
  tp.trace_id,
  tp.total_duration_seconds,
  tp.span_count,
  te.error_count,
  te.error_messages
FROM trace_perf tp
JOIN trace_errors te ON tp.trace_id = te.trace_id
WHERE TIMESTAMP_DIFF(TIMESTAMP_SECONDS(0) + INTERVAL CAST(tp.total_duration_seconds AS INT64) SECOND, TIMESTAMP_SECONDS(0), SECOND) > 5  -- > 5 seconds
ORDER BY tp.total_duration_seconds DESC
LIMIT 50
```

### 4. Service Dependency Analysis

#### Build Service Call Graph
```sql
-- Create service dependency map from traces
SELECT
  caller_service,
  callee_service,
  COUNT(*) as call_count,
  APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(50)] as p50_latency,
  APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(95)] as p95_latency
FROM (
  SELECT
    parent.span_name as caller_service,
    child.span_name as callee_service,
    child.span_duration_ms
  FROM `PROJECT.DATASET.traces` parent
  JOIN `PROJECT.DATASET.traces` child
    ON parent.trace_id = child.trace_id
    AND parent.span_id = child.parent_span_id
  WHERE parent.start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
)
GROUP BY caller_service, callee_service
HAVING call_count > 10
ORDER BY call_count DESC
LIMIT 100
```

#### Critical Path Analysis at Scale
```sql
-- Find spans on critical path (longest duration in each trace)
WITH ranked_spans AS (
  SELECT
    trace_id,
    span_name,
    span_duration_ms,
    ROW_NUMBER() OVER (PARTITION BY trace_id ORDER BY span_duration_ms DESC) as rank
  FROM `PROJECT.DATASET.traces`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
)
SELECT
  span_name,
  COUNT(*) as times_on_critical_path,
  AVG(span_duration_ms) as avg_duration,
  APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(95)] as p95_duration
FROM ranked_spans
WHERE rank = 1  -- Longest span in each trace
GROUP BY span_name
ORDER BY times_on_critical_path DESC
LIMIT 20
```

### 5. User Experience Analysis

#### Analyze by HTTP Status Code
```sql
-- Performance by HTTP status code
SELECT
  CAST(JSON_EXTRACT_SCALAR(json_payload, '$.http_request.status') AS INT64) as status_code,
  COUNT(*) as request_count,
  APPROX_QUANTILES(
    CAST(JSON_EXTRACT_SCALAR(json_payload, '$.http_request.latency_seconds') AS FLOAT64) * 1000,
    100
  )[OFFSET(95)] as p95_latency_ms,
  COUNT(DISTINCT REGEXP_EXTRACT(trace, r'traces/(.+)')) as unique_traces
FROM `PROJECT.DATASET.logs`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
  AND JSON_EXTRACT_SCALAR(json_payload, '$.http_request.status') IS NOT NULL
GROUP BY status_code
ORDER BY status_code
```

#### Geo Performance Analysis
```sql
-- Performance by region/location
WITH trace_locations AS (
  SELECT
    trace_id,
    MAX(span_duration_ms) as max_span_duration,
    ARRAY_AGG(
      label.value
      ORDER BY label.key
      LIMIT 1
    )[SAFE_OFFSET(0)] as region
  FROM `PROJECT.DATASET.traces`,
  UNNEST(labels) as label
  WHERE label.key = 'cloud.region'
    AND start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  GROUP BY trace_id
)
SELECT
  region,
  COUNT(*) as trace_count,
  APPROX_QUANTILES(max_span_duration, 100)[OFFSET(50)] as p50,
  APPROX_QUANTILES(max_span_duration, 100)[OFFSET(95)] as p95,
  APPROX_QUANTILES(max_span_duration, 100)[OFFSET(99)] as p99
FROM trace_locations
WHERE region IS NOT NULL
GROUP BY region
ORDER BY p95 DESC
```

### 6. Time-Series Analysis

#### Hourly Request Rate & Latency
```sql
-- Hourly trends for the last 7 days
SELECT
  TIMESTAMP_TRUNC(start_time, HOUR) as hour,
  COUNT(*) as request_count,
  APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(50)] as p50_latency,
  APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(95)] as p95_latency,
  COUNTIF(
    EXISTS(SELECT 1 FROM UNNEST(labels) WHERE key LIKE '%error%')
  ) as error_count
FROM `PROJECT.DATASET.traces`
WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND parent_span_id IS NULL  -- Root spans only
GROUP BY hour
ORDER BY hour DESC
```

#### Detect Anomalies Using Z-Score
```sql
-- Detect latency anomalies using statistical methods
WITH daily_stats AS (
  SELECT
    DATE(start_time) as date,
    span_name,
    AVG(span_duration_ms) as mean_duration,
    STDDEV(span_duration_ms) as stddev_duration,
    COUNT(*) as sample_count
  FROM `PROJECT.DATASET.traces`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  GROUP BY date, span_name
  HAVING sample_count > 10
),
current_performance AS (
  SELECT
    span_name,
    AVG(span_duration_ms) as current_mean
  FROM `PROJECT.DATASET.traces`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
  GROUP BY span_name
)
SELECT
  ds.span_name,
  ds.date,
  ds.mean_duration as historical_mean,
  ds.stddev_duration,
  cp.current_mean,
  (cp.current_mean - ds.mean_duration) / ds.stddev_duration as z_score
FROM daily_stats ds
JOIN current_performance cp ON ds.span_name = cp.span_name
WHERE ABS((cp.current_mean - ds.mean_duration) / ds.stddev_duration) > 2  -- Z-score > 2
  AND ds.date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
ORDER BY ABS((cp.current_mean - ds.mean_duration) / ds.stddev_duration) DESC
LIMIT 50
```

## Advanced Patterns

### Join Traces with Logs for Complete Context
```sql
-- Combine trace performance with log errors
WITH trace_perf AS (
  SELECT
    trace_id,
    MAX(end_time) - MIN(start_time) as duration_seconds,
    STRING_AGG(DISTINCT span_name ORDER BY span_name) as spans_involved
  FROM `PROJECT.DATASET.traces`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
  GROUP BY trace_id
),
trace_logs AS (
  SELECT
    REGEXP_EXTRACT(trace, r'traces/(.+)') as trace_id,
    ARRAY_AGG(
      STRUCT(
        timestamp,
        severity,
        JSON_EXTRACT_SCALAR(json_payload, '$.message') as message
      )
      ORDER BY timestamp
    ) as log_entries
  FROM `PROJECT.DATASET.logs`
  WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
    AND trace IS NOT NULL
  GROUP BY trace_id
)
SELECT
  tp.trace_id,
  tp.duration_seconds,
  tp.spans_involved,
  tl.log_entries
FROM trace_perf tp
JOIN trace_logs tl ON tp.trace_id = tl.trace_id
WHERE TIMESTAMP_DIFF(TIMESTAMP_SECONDS(0) + INTERVAL CAST(tp.duration_seconds AS INT64) SECOND, TIMESTAMP_SECONDS(0), SECOND) > 3
ORDER BY tp.duration_seconds DESC
LIMIT 20
```

### Create Materialized Views for Faster Queries
```sql
-- Create a daily summary table for faster analysis
CREATE OR REPLACE TABLE `PROJECT.DATASET.daily_trace_summary`
PARTITION BY date
AS
SELECT
  DATE(start_time) as date,
  span_name,
  COUNT(*) as request_count,
  APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(50)] as p50,
  APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(95)] as p95,
  APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(99)] as p99,
  AVG(span_duration_ms) as mean,
  STDDEV(span_duration_ms) as stddev,
  MIN(span_duration_ms) as min,
  MAX(span_duration_ms) as max
FROM `PROJECT.DATASET.traces`
WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
GROUP BY date, span_name
```

## Best Practices

### 1. Query Optimization
- ✅ Always use `TIMESTAMP` filters to leverage partitioning
- ✅ Use `APPROX_QUANTILES` instead of exact percentiles for large datasets
- ✅ Limit result sets with `LIMIT` clause
- ✅ Create materialized views for repeated queries
- ✅ Use `ARRAY_AGG(...LIMIT N)` to limit array sizes

### 2. Cost Management
- ⚠️ BigQuery charges by data scanned
- ⚠️ Use partitioned tables (by date)
- ⚠️ Avoid `SELECT *` - specify columns
- ⚠️ Set up cost alerts
- ⚠️ Use preview/dry-run to check query cost

### 3. Performance
- 🚀 Partition tables by timestamp
- 🚀 Cluster tables by frequently filtered columns (span_name, trace_id)
- 🚀 Use streaming inserts for real-time analysis
- 🚀 Schedule queries to pre-compute summaries

### 4. Data Retention
- Set up table expiration for raw data (90 days)
- Keep aggregated summaries longer (365 days)
- Archive critical traces separately

## Integration with SRE Agent

### Example: Using BigQuery from the Agent

```python
# Agent determines it needs large-scale analysis
if num_traces_needed > 50:
    # Use BigQuery instead of Trace API
    query = """
    SELECT trace_id, MAX(span_duration_ms) as max_duration
    FROM `PROJECT.DATASET.traces`
    WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
      AND span_name = 'my-operation'
    ORDER BY max_duration DESC
    LIMIT 20
    """

    slow_traces = execute_sql(project_id, query)

    # Now analyze with tools
    for trace_info in slow_traces:
        trace = fetch_trace(project_id, trace_info['trace_id'])
        # ... analysis
```

### Example: Combining BigQuery with Pattern Analysis

```python
# 1. Get sample traces from BigQuery
query = """
SELECT trace_id
FROM `PROJECT.DATASET.traces`
WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
LIMIT 50
"""
trace_ids = execute_sql(project_id, query)

# 2. Fetch traces
traces = [fetch_trace(project_id, tid) for tid in trace_ids]

# 3. Use pattern analysis tool
patterns = analyze_trace_patterns(traces)

# 4. Get detailed info about patterns from BigQuery
if patterns["patterns"]["recurring_slowdowns"]:
    span_name = patterns["patterns"]["recurring_slowdowns"][0]["span_name"]

    detail_query = f"""
    SELECT
      DATE(start_time) as date,
      AVG(span_duration_ms) as avg_duration
    FROM `PROJECT.DATASET.traces`
    WHERE span_name = '{span_name}'
      AND start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
    GROUP BY date
    ORDER BY date
    """

    trend = execute_sql(project_id, detail_query)
```

## Resources

- [BigQuery SQL Reference](https://cloud.google.com/bigquery/docs/reference/standard-sql)
- [Cloud Trace Export to BigQuery](https://cloud.google.com/trace/docs/exporting-to-bigquery)
- [Cloud Logging Export to BigQuery](https://cloud.google.com/logging/docs/export/bigquery)
- [BigQuery Pricing](https://cloud.google.com/bigquery/pricing)
