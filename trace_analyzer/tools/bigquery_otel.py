"""BigQuery-powered tools for OpenTelemetry trace analysis.

This module provides sophisticated analysis capabilities using BigQuery
to query trace data at scale. It assumes traces are exported to BigQuery
using the OpenTelemetry schema.

Standard OpenTelemetry schema in BigQuery:
- Table: `<dataset>.otel_traces`
- Key fields:
  - trace_id: Unique trace identifier
  - span_id: Unique span identifier
  - parent_span_id: Parent span reference
  - span_name: Operation name
  - start_time: Span start timestamp
  - end_time: Span end timestamp
  - duration: Span duration in nanoseconds
  - status_code: OK, ERROR, UNSET
  - attributes: Key-value pairs (STRUCT or JSON)
  - resource_attributes: Resource metadata
  - service_name: Extracted from resource.service.name
"""

import json
import logging
from typing import Any

from ..decorators import adk_tool

logger = logging.getLogger(__name__)


@adk_tool
def analyze_aggregate_metrics(
    dataset_id: str,
    table_name: str = "otel_traces",
    time_window_hours: int = 24,
    service_name: str | None = None,
    operation_name: str | None = None,
    min_duration_ms: float | None = None,
    group_by: str = "service_name",
) -> str:
    """
    Performs broad aggregate analysis of trace data using BigQuery.

    This is the first step in SRE analysis: get the big picture before drilling down.
    Analyzes metrics like request rate, error rate, latency percentiles across services.

    Args:
        dataset_id: BigQuery dataset ID (e.g., 'my_project.telemetry')
        table_name: Table name containing OTEL traces
        time_window_hours: How many hours back to analyze
        service_name: Optional filter for specific service
        operation_name: Optional filter for specific operation
        min_duration_ms: Optional filter for minimum duration
        group_by: How to group results (service_name, operation_name, status_code)

    Returns:
        JSON with aggregate metrics including:
        - Request counts
        - Error rates
        - Latency percentiles (P50, P95, P99)
        - Top slowest operations
        - Services with highest error rates

    Example SQL that will be generated for BigQuery MCP:
    ```sql
    SELECT
      service_name,
      COUNT(*) as request_count,
      COUNTIF(status_code = 'ERROR') as error_count,
      ROUND(COUNTIF(status_code = 'ERROR') / COUNT(*) * 100, 2) as error_rate_pct,
      APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(50)] as p50_ms,
      APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(95)] as p95_ms,
      APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(99)] as p99_ms,
      AVG(duration / 1000000) as avg_duration_ms
    FROM `{dataset_id}.{table_name}`
    WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours} HOUR)
      AND parent_span_id IS NULL  -- Root spans only
    GROUP BY service_name
    ORDER BY error_rate_pct DESC, p99_ms DESC
    ```

    Note: This tool returns the SQL query to be executed via BigQuery MCP tools.
    The agent should use the BigQuery MCP 'execute_sql' tool with this query.
    """
    # Build WHERE clause
    where_conditions = [
        f"start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)",
        "parent_span_id IS NULL  -- Root spans only for aggregate metrics"
    ]

    if service_name:
        where_conditions.append(f"service_name = '{service_name}'")

    if operation_name:
        where_conditions.append(f"span_name = '{operation_name}'")

    if min_duration_ms:
        # Convert ms to nanoseconds
        min_duration_ns = int(min_duration_ms * 1_000_000)
        where_conditions.append(f"duration >= {min_duration_ns}")

    where_clause = " AND ".join(where_conditions)

    # Build query
    query = f"""
SELECT
  {group_by},
  COUNT(*) as request_count,
  COUNTIF(status_code = 'ERROR') as error_count,
  ROUND(COUNTIF(status_code = 'ERROR') / COUNT(*) * 100, 2) as error_rate_pct,
  ROUND(APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(50)], 2) as p50_ms,
  ROUND(APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(95)], 2) as p95_ms,
  ROUND(APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(99)], 2) as p99_ms,
  ROUND(AVG(duration / 1000000), 2) as avg_duration_ms,
  MIN(start_time) as first_seen,
  MAX(start_time) as last_seen
FROM `{dataset_id}.{table_name}`
WHERE {where_clause}
GROUP BY {group_by}
ORDER BY error_rate_pct DESC, p99_ms DESC
LIMIT 50
"""

    return json.dumps({
        "analysis_type": "aggregate_metrics",
        "sql_query": query.strip(),
        "description": f"Aggregate metrics grouped by {group_by} for last {time_window_hours}h",
        "next_steps": [
            "Execute this query using BigQuery MCP execute_sql tool",
            "Review services with high error rates or P99 latency",
            "Use find_exemplar_traces to get specific trace IDs for investigation"
        ]
    })


@adk_tool
def find_exemplar_traces(
    dataset_id: str,
    table_name: str = "otel_traces",
    time_window_hours: int = 24,
    service_name: str | None = None,
    operation_name: str | None = None,
    selection_strategy: str = "outliers",
    limit: int = 10,
) -> str:
    """
    Finds exemplar traces using BigQuery for detailed investigation.

    This is step 2: After aggregate analysis shows issues, find specific traces
    that represent different patterns (baseline, slow, error, etc.)

    Args:
        dataset_id: BigQuery dataset ID
        table_name: Table name containing OTEL traces
        time_window_hours: How many hours back to search
        service_name: Optional filter for specific service
        operation_name: Optional filter for specific operation
        selection_strategy: How to select exemplars:
            - 'outliers': Slowest traces (P99+)
            - 'errors': Traces with errors
            - 'baseline': Typical traces (P50)
            - 'comparison': Both baseline and outliers
        limit: Number of exemplars to return

    Returns:
        JSON with SQL query to find exemplar trace IDs.

    The query returns trace IDs with metadata like duration, error status,
    making them suitable for detailed diff analysis with trace_analyzer tools.
    """
    where_conditions = [
        f"start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)",
        "parent_span_id IS NULL"
    ]

    if service_name:
        where_conditions.append(f"service_name = '{service_name}'")

    if operation_name:
        where_conditions.append(f"span_name = '{operation_name}'")

    where_clause = " AND ".join(where_conditions)

    # Build query based on selection strategy
    if selection_strategy == "outliers":
        # Find slowest traces (P95+)
        query = f"""
WITH duration_stats AS (
  SELECT
    APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(95)] as p95_ms
  FROM `{dataset_id}.{table_name}`
  WHERE {where_clause}
)
SELECT
  t.trace_id,
  t.span_name as operation,
  t.service_name,
  ROUND(t.duration / 1000000, 2) as duration_ms,
  t.status_code,
  t.start_time,
  ROUND((t.duration / 1000000 - s.p95_ms) / s.p95_ms * 100, 2) as pct_above_p95
FROM `{dataset_id}.{table_name}` t
CROSS JOIN duration_stats s
WHERE {where_clause}
  AND t.duration / 1000000 >= s.p95_ms
ORDER BY t.duration DESC
LIMIT {limit}
"""

    elif selection_strategy == "errors":
        query = f"""
SELECT
  trace_id,
  span_name as operation,
  service_name,
  ROUND(duration / 1000000, 2) as duration_ms,
  status_code,
  start_time,
  'error_trace' as selection_reason
FROM `{dataset_id}.{table_name}`
WHERE {where_clause}
  AND status_code = 'ERROR'
ORDER BY start_time DESC
LIMIT {limit}
"""

    elif selection_strategy == "baseline":
        # Find typical traces around P50
        query = f"""
WITH duration_stats AS (
  SELECT
    APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(50)] as p50_ms
  FROM `{dataset_id}.{table_name}`
  WHERE {where_clause}
)
SELECT
  t.trace_id,
  t.span_name as operation,
  t.service_name,
  ROUND(t.duration / 1000000, 2) as duration_ms,
  t.status_code,
  t.start_time,
  'baseline_p50' as selection_reason
FROM `{dataset_id}.{table_name}` t
CROSS JOIN duration_stats s
WHERE {where_clause}
  AND t.status_code != 'ERROR'
  AND ABS(t.duration / 1000000 - s.p50_ms) < s.p50_ms * 0.1  -- Within 10% of P50
ORDER BY ABS(t.duration / 1000000 - s.p50_ms)
LIMIT {limit}
"""

    elif selection_strategy == "comparison":
        # Get both baseline and outliers
        query = f"""
WITH duration_stats AS (
  SELECT
    APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(50)] as p50_ms,
    APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(95)] as p95_ms
  FROM `{dataset_id}.{table_name}`
  WHERE {where_clause}
),
baseline_traces AS (
  SELECT
    t.trace_id,
    t.span_name as operation,
    t.service_name,
    ROUND(t.duration / 1000000, 2) as duration_ms,
    t.status_code,
    t.start_time,
    'baseline_p50' as selection_reason
  FROM `{dataset_id}.{table_name}` t
  CROSS JOIN duration_stats s
  WHERE {where_clause}
    AND t.status_code != 'ERROR'
    AND ABS(t.duration / 1000000 - s.p50_ms) < s.p50_ms * 0.1
  ORDER BY ABS(t.duration / 1000000 - s.p50_ms)
  LIMIT {limit // 2}
),
outlier_traces AS (
  SELECT
    t.trace_id,
    t.span_name as operation,
    t.service_name,
    ROUND(t.duration / 1000000, 2) as duration_ms,
    t.status_code,
    t.start_time,
    'outlier_p95' as selection_reason
  FROM `{dataset_id}.{table_name}` t
  CROSS JOIN duration_stats s
  WHERE {where_clause}
    AND t.duration / 1000000 >= s.p95_ms
  ORDER BY t.duration DESC
  LIMIT {limit // 2}
)
SELECT * FROM baseline_traces
UNION ALL
SELECT * FROM outlier_traces
ORDER BY selection_reason, duration_ms
"""
    else:
        return json.dumps({"error": f"Unknown selection_strategy: {selection_strategy}"})

    return json.dumps({
        "analysis_type": "exemplar_selection",
        "selection_strategy": selection_strategy,
        "sql_query": query.strip(),
        "description": f"Find {limit} exemplar traces using '{selection_strategy}' strategy",
        "next_steps": [
            "Execute this query using BigQuery MCP execute_sql tool",
            "Extract trace_id values from results",
            "Use fetch_trace to get full trace details",
            "Use run_triage_analysis to compare baseline vs outlier traces"
        ]
    })


@adk_tool
def correlate_logs_with_trace(
    dataset_id: str,
    trace_id: str,
    log_table_name: str = "otel_logs",
    include_nearby_logs: bool = True,
    time_window_seconds: int = 30,
) -> str:
    """
    Finds logs correlated with a specific trace for root cause analysis.

    This is crucial for deep-dive: traces show WHAT happened, logs show WHY.
    Queries BigQuery for logs that share the same trace_id or occurred nearby.

    Args:
        dataset_id: BigQuery dataset ID
        trace_id: The trace ID to correlate logs with
        log_table_name: Table name containing OTEL logs
        include_nearby_logs: If True, include logs from same service around the same time
        time_window_seconds: Time window for nearby logs (default 30s)

    Returns:
        JSON with SQL query to find correlated logs.

    OpenTelemetry logs schema typically includes:
    - trace_id: Correlation with traces
    - severity_text: ERROR, WARN, INFO, etc.
    - body: Log message
    - resource_attributes: Service metadata
    - timestamp: When the log occurred
    """
    # First get trace timing to find nearby logs
    query = f"""
WITH trace_context AS (
  SELECT
    MIN(start_time) as trace_start,
    MAX(end_time) as trace_end,
    ANY_VALUE(service_name) as service_name
  FROM `{dataset_id}.otel_traces`
  WHERE trace_id = '{trace_id}'
    AND parent_span_id IS NULL
),
direct_logs AS (
  -- Logs directly correlated via trace_id
  SELECT
    l.timestamp,
    l.severity_text as severity,
    l.body as message,
    l.resource_attributes.service_name as service,
    'direct_correlation' as correlation_type,
    l.trace_id
  FROM `{dataset_id}.{log_table_name}` l
  WHERE l.trace_id = '{trace_id}'
)
"""

    if include_nearby_logs:
        query += f""",
nearby_logs AS (
  -- Logs from same service around the same time (useful for errors not tagged with trace_id)
  SELECT
    l.timestamp,
    l.severity_text as severity,
    l.body as message,
    l.resource_attributes.service_name as service,
    'temporal_correlation' as correlation_type,
    l.trace_id
  FROM `{dataset_id}.{log_table_name}` l
  CROSS JOIN trace_context t
  WHERE l.resource_attributes.service_name = t.service_name
    AND l.timestamp >= TIMESTAMP_SUB(t.trace_start, INTERVAL {time_window_seconds} SECOND)
    AND l.timestamp <= TIMESTAMP_ADD(t.trace_end, INTERVAL {time_window_seconds} SECOND)
    AND l.severity_text IN ('ERROR', 'CRITICAL', 'WARN')
    AND l.trace_id != '{trace_id}'  -- Don't duplicate direct logs
  LIMIT 20
)
SELECT * FROM direct_logs
UNION ALL
SELECT * FROM nearby_logs
ORDER BY timestamp
"""
    else:
        query += """
SELECT * FROM direct_logs
ORDER BY timestamp
"""

    return json.dumps({
        "analysis_type": "log_correlation",
        "trace_id": trace_id,
        "sql_query": query.strip(),
        "description": f"Find logs correlated with trace {trace_id}",
        "next_steps": [
            "Execute this query using BigQuery MCP execute_sql tool",
            "Look for ERROR or WARN severity logs",
            "Check log messages for exceptions, timeouts, or error codes",
            "Correlate log timestamps with slow spans from trace analysis"
        ]
    })


@adk_tool
def compare_time_periods(
    dataset_id: str,
    table_name: str = "otel_traces",
    baseline_hours_ago_start: int = 48,
    baseline_hours_ago_end: int = 24,
    anomaly_hours_ago_start: int = 24,
    anomaly_hours_ago_end: int = 0,
    service_name: str | None = None,
    operation_name: str | None = None,
) -> str:
    """
    Compares trace metrics between two time periods to detect degradations.

    This helps answer: "When did things start going wrong?"
    Compares a baseline period (known good) vs anomaly period (suspected bad).

    Args:
        dataset_id: BigQuery dataset ID
        table_name: Table name containing OTEL traces
        baseline_hours_ago_start: Baseline period start (hours ago)
        baseline_hours_ago_end: Baseline period end (hours ago)
        anomaly_hours_ago_start: Anomaly period start (hours ago)
        anomaly_hours_ago_end: Anomaly period end (hours ago)
        service_name: Optional filter for specific service
        operation_name: Optional filter for specific operation

    Returns:
        JSON with SQL query comparing the two periods.

    Example: Compare yesterday (baseline) vs today (anomaly)
    - baseline_hours_ago_start=48, baseline_hours_ago_end=24 (yesterday)
    - anomaly_hours_ago_start=24, anomaly_hours_ago_end=0 (today)
    """
    where_filter = ""
    if service_name:
        where_filter += f"AND service_name = '{service_name}'\n  "
    if operation_name:
        where_filter += f"AND span_name = '{operation_name}'\n  "

    query = f"""
WITH baseline_period AS (
  SELECT
    'baseline' as period,
    COUNT(*) as request_count,
    COUNTIF(status_code = 'ERROR') as error_count,
    ROUND(COUNTIF(status_code = 'ERROR') / COUNT(*) * 100, 2) as error_rate_pct,
    ROUND(APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(50)], 2) as p50_ms,
    ROUND(APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(95)], 2) as p95_ms,
    ROUND(APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(99)], 2) as p99_ms,
    ROUND(AVG(duration / 1000000), 2) as avg_ms
  FROM `{dataset_id}.{table_name}`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {baseline_hours_ago_start} HOUR)
    AND start_time < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {baseline_hours_ago_end} HOUR)
    AND parent_span_id IS NULL
    {where_filter}
),
anomaly_period AS (
  SELECT
    'anomaly' as period,
    COUNT(*) as request_count,
    COUNTIF(status_code = 'ERROR') as error_count,
    ROUND(COUNTIF(status_code = 'ERROR') / COUNT(*) * 100, 2) as error_rate_pct,
    ROUND(APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(50)], 2) as p50_ms,
    ROUND(APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(95)], 2) as p95_ms,
    ROUND(APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(99)], 2) as p99_ms,
    ROUND(AVG(duration / 1000000), 2) as avg_ms
  FROM `{dataset_id}.{table_name}`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {anomaly_hours_ago_start} HOUR)
    AND start_time < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {anomaly_hours_ago_end} HOUR)
    AND parent_span_id IS NULL
    {where_filter}
),
combined AS (
  SELECT * FROM baseline_period
  UNION ALL
  SELECT * FROM anomaly_period
)
SELECT
  period,
  request_count,
  error_count,
  error_rate_pct,
  p50_ms,
  p95_ms,
  p99_ms,
  avg_ms,
  -- Calculate deltas for anomaly period
  LAG(p95_ms) OVER (ORDER BY period) as baseline_p95_ms,
  p95_ms - LAG(p95_ms) OVER (ORDER BY period) as p95_delta_ms,
  ROUND((p95_ms - LAG(p95_ms) OVER (ORDER BY period)) / LAG(p95_ms) OVER (ORDER BY period) * 100, 1) as p95_change_pct,
  error_rate_pct - LAG(error_rate_pct) OVER (ORDER BY period) as error_rate_delta
FROM combined
ORDER BY period
"""

    return json.dumps({
        "analysis_type": "time_period_comparison",
        "sql_query": query.strip(),
        "baseline_period": f"{baseline_hours_ago_start}h ago to {baseline_hours_ago_end}h ago",
        "anomaly_period": f"{anomaly_hours_ago_start}h ago to {anomaly_hours_ago_end}h ago",
        "description": "Compare metrics between baseline and anomaly time periods",
        "next_steps": [
            "Execute this query using BigQuery MCP execute_sql tool",
            "Look for significant deltas in p95_change_pct or error_rate_delta",
            "If degradation is confirmed, use find_exemplar_traces for each period",
            "Use run_triage_analysis to compare exemplars and find root cause"
        ]
    })


@adk_tool
def detect_trend_changes(
    dataset_id: str,
    table_name: str = "otel_traces",
    time_window_hours: int = 72,
    bucket_hours: int = 1,
    service_name: str | None = None,
    metric: str = "p95",
) -> str:
    """
    Detects when performance trends changed using time-series analysis.

    This helps answer: "When exactly did the slowdown start?"
    Breaks down time window into buckets and shows metric trends.

    Args:
        dataset_id: BigQuery dataset ID
        table_name: Table name containing OTEL traces
        time_window_hours: Total time window to analyze
        bucket_hours: Size of each time bucket for trending
        service_name: Optional filter for specific service
        metric: Which metric to track (p95, p99, error_rate, throughput)

    Returns:
        JSON with SQL query showing metric trends over time.
    """
    where_filter = ""
    if service_name:
        where_filter = f"AND service_name = '{service_name}'"

    # Build metric calculation based on requested metric
    if metric == "p95":
        metric_calc = "ROUND(APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(95)], 2) as metric_value"
        metric_name = "p95_latency_ms"
    elif metric == "p99":
        metric_calc = "ROUND(APPROX_QUANTILES(duration / 1000000, 100)[OFFSET(99)], 2) as metric_value"
        metric_name = "p99_latency_ms"
    elif metric == "error_rate":
        metric_calc = "ROUND(COUNTIF(status_code = 'ERROR') / COUNT(*) * 100, 2) as metric_value"
        metric_name = "error_rate_pct"
    elif metric == "throughput":
        metric_calc = "COUNT(*) as metric_value"
        metric_name = "request_count"
    else:
        return json.dumps({"error": f"Unknown metric: {metric}. Use p95, p99, error_rate, or throughput"})

    query = f"""
WITH time_buckets AS (
  SELECT
    TIMESTAMP_TRUNC(start_time, HOUR) as time_bucket,
    {metric_calc},
    COUNT(*) as sample_size
  FROM `{dataset_id}.{table_name}`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)
    AND parent_span_id IS NULL
    {where_filter}
  GROUP BY time_bucket
  HAVING sample_size >= 10  -- Need sufficient samples per bucket
  ORDER BY time_bucket
),
with_moving_avg AS (
  SELECT
    time_bucket,
    metric_value,
    sample_size,
    AVG(metric_value) OVER (
      ORDER BY time_bucket
      ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) as moving_avg_3h,
    metric_value - LAG(metric_value, 1) OVER (ORDER BY time_bucket) as delta_1h,
    ROUND((metric_value - LAG(metric_value, 1) OVER (ORDER BY time_bucket)) /
          LAG(metric_value, 1) OVER (ORDER BY time_bucket) * 100, 1) as pct_change_1h
  FROM time_buckets
)
SELECT
  time_bucket,
  metric_value as {metric_name},
  sample_size,
  ROUND(moving_avg_3h, 2) as moving_avg_3h,
  delta_1h,
  pct_change_1h,
  -- Flag significant changes (>20% jump)
  CASE
    WHEN ABS(pct_change_1h) >= 20 THEN 'SIGNIFICANT_CHANGE'
    WHEN ABS(pct_change_1h) >= 10 THEN 'MODERATE_CHANGE'
    ELSE 'STABLE'
  END as change_magnitude
FROM with_moving_avg
ORDER BY time_bucket DESC
"""

    return json.dumps({
        "analysis_type": "trend_detection",
        "sql_query": query.strip(),
        "metric": metric,
        "time_window_hours": time_window_hours,
        "bucket_hours": bucket_hours,
        "description": f"Detect trend changes in {metric} over {time_window_hours}h",
        "next_steps": [
            "Execute this query using BigQuery MCP execute_sql tool",
            "Look for rows with change_magnitude = 'SIGNIFICANT_CHANGE'",
            "Note the time_bucket when degradation started",
            "Use compare_time_periods with before/after time ranges",
            "Use find_exemplar_traces from the degraded time period"
        ]
    })
