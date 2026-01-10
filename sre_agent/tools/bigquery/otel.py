"""BigQuery-powered tools for OpenTelemetry data analysis.

This module provides sophisticated analysis capabilities using BigQuery
to query trace and log data at scale. It assumes data is exported to BigQuery
using the OpenTelemetry schema.

Google Cloud Observability OpenTelemetry schema (_AllSpans table):
- Table: `<dataset>._AllSpans` (or custom table name)
- Key fields:
  - trace_id: Unique trace identifier (128-bit hex string)
  - span_id: Unique span identifier (64-bit hex string)
  - parent_span_id: Parent span reference (NULL for root spans)
  - name: Span/operation name
  - start_time: Span start timestamp
  - end_time: Span end timestamp
  - duration_nano: Span duration in nanoseconds
  - status: RECORD with code (0=UNSET, 1=OK, 2=ERROR) and message
  - kind: Span kind (1=INTERNAL, 2=SERVER, 3=CLIENT, 4=PRODUCER, 5=CONSUMER)
  - attributes: JSON key-value pairs
  - resource: RECORD with attributes (service.name, host.name, etc.)
"""

import json
import logging

from ..common import adk_tool

logger = logging.getLogger(__name__)


@adk_tool
def analyze_aggregate_metrics(
    dataset_id: str,
    table_name: str,
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
        JSON with SQL query and metadata for execution via BigQuery MCP.
    """
    where_conditions = [
        f"start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)",
        "parent_span_id IS NULL  -- Root spans only for aggregate metrics",
    ]

    if service_name:
        where_conditions.append(
            f"JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') = '{service_name}'"
        )

    if operation_name:
        where_conditions.append(f"name = '{operation_name}'")

    if min_duration_ms:
        min_duration_ns = int(min_duration_ms * 1_000_000)
        where_conditions.append(f"duration_nano >= {min_duration_ns}")

    where_clause = " AND ".join(where_conditions)

    group_by_field = group_by
    if group_by == "service_name":
        group_by_field = "JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name')"
    elif group_by == "operation_name":
        group_by_field = "name"
    elif group_by == "status_code":
        group_by_field = "status.code"

    query = f"""
SELECT
  {group_by_field} as {group_by},
  COUNT(*) as request_count,
  COUNTIF(status.code = 2) as error_count,
  ROUND(COUNTIF(status.code = 2) / COUNT(*) * 100, 2) as error_rate_pct,
  ROUND(APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(50)], 2) as p50_ms,
  ROUND(APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(95)], 2) as p95_ms,
  ROUND(APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(99)], 2) as p99_ms,
  ROUND(AVG(duration_nano / 1000000), 2) as avg_duration_ms,
  MIN(start_time) as first_seen,
  MAX(start_time) as last_seen
FROM `{dataset_id}.{table_name}`
WHERE {where_clause}
GROUP BY {group_by}
ORDER BY error_rate_pct DESC, p99_ms DESC
LIMIT 50
"""

    logger.info(f"Generated Aggregate Analysis SQL:\n{query.strip()}")

    return json.dumps(
        {
            "analysis_type": "aggregate_metrics",
            "sql_query": query.strip(),
            "description": f"Aggregate metrics grouped by {group_by} for last {time_window_hours}h",
            "next_steps": [
                "Execute this query using BigQuery MCP execute_sql tool",
                "Review services with high error rates or P99 latency",
                "Use find_exemplar_traces to get specific trace IDs for investigation",
            ],
        }
    )


@adk_tool
def find_exemplar_traces(
    dataset_id: str,
    table_name: str,
    time_window_hours: int = 24,
    service_name: str | None = None,
    operation_name: str | None = None,
    selection_strategy: str = "outliers",
    limit: int = 10,
) -> str:
    """
    Finds exemplar traces using BigQuery for detailed investigation.

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
    """
    where_conditions = [
        f"start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)",
        "parent_span_id IS NULL",
    ]

    if service_name:
        where_conditions.append(
            f"JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') = '{service_name}'"
        )

    if operation_name:
        where_conditions.append(f"name = '{operation_name}'")

    where_clause = " AND ".join(where_conditions)

    if selection_strategy == "outliers":
        query = f"""
WITH duration_stats AS (
  SELECT
    APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(95)] as p95_ms
  FROM `{dataset_id}.{table_name}`
  WHERE {where_clause}
)
SELECT
  t.trace_id,
  t.name as operation,
  JSON_EXTRACT_SCALAR(t.resource.attributes, '$.service.name') as service_name,
  ROUND(t.duration_nano / 1000000, 2) as duration_ms,
  t.status.code as status_code,
  t.start_time,
  ROUND((t.duration_nano / 1000000 - s.p95_ms) / s.p95_ms * 100, 2) as pct_above_p95
FROM `{dataset_id}.{table_name}` t
CROSS JOIN duration_stats s
WHERE {where_clause}
  AND t.duration_nano / 1000000 >= s.p95_ms
ORDER BY t.duration_nano DESC
LIMIT {limit}
"""

    elif selection_strategy == "errors":
        query = f"""
SELECT
  trace_id,
  name as operation,
  JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') as service_name,
  ROUND(duration_nano / 1000000, 2) as duration_ms,
  status.code as status_code,
  status.message as error_message,
  start_time,
  'error_trace' as selection_reason
FROM `{dataset_id}.{table_name}`
WHERE {where_clause}
  AND status.code = 2  -- ERROR
ORDER BY start_time DESC
LIMIT {limit}
"""

    elif selection_strategy == "baseline":
        query = f"""
WITH duration_stats AS (
  SELECT
    APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(50)] as p50_ms
  FROM `{dataset_id}.{table_name}`
  WHERE {where_clause}
)
SELECT
  t.trace_id,
  t.name as operation,
  JSON_EXTRACT_SCALAR(t.resource.attributes, '$.service.name') as service_name,
  ROUND(t.duration_nano / 1000000, 2) as duration_ms,
  t.status.code as status_code,
  t.start_time,
  'baseline_p50' as selection_reason
FROM `{dataset_id}.{table_name}` t
CROSS JOIN duration_stats s
WHERE {where_clause}
  AND t.status.code != 2  -- Not ERROR
  AND ABS(t.duration_nano / 1000000 - s.p50_ms) < s.p50_ms * 0.1
ORDER BY ABS(t.duration_nano / 1000000 - s.p50_ms)
LIMIT {limit}
"""

    elif selection_strategy == "comparison":
        query = f"""
WITH duration_stats AS (
  SELECT
    APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(50)] as p50_ms,
    APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(95)] as p95_ms
  FROM `{dataset_id}.{table_name}`
  WHERE {where_clause}
),
baseline_traces AS (
  SELECT
    t.trace_id,
    t.name as operation,
    JSON_EXTRACT_SCALAR(t.resource.attributes, '$.service.name') as service_name,
    ROUND(t.duration_nano / 1000000, 2) as duration_ms,
    t.status.code as status_code,
    t.start_time,
    'baseline_p50' as selection_reason
  FROM `{dataset_id}.{table_name}` t
  CROSS JOIN duration_stats s
  WHERE {where_clause}
    AND t.status.code != 2
    AND ABS(t.duration_nano / 1000000 - s.p50_ms) < s.p50_ms * 0.1
  ORDER BY ABS(t.duration_nano / 1000000 - s.p50_ms)
  LIMIT {limit // 2}
),
outlier_traces AS (
  SELECT
    t.trace_id,
    t.name as operation,
    JSON_EXTRACT_SCALAR(t.resource.attributes, '$.service.name') as service_name,
    ROUND(t.duration_nano / 1000000, 2) as duration_ms,
    t.status.code as status_code,
    t.start_time,
    'outlier_p95' as selection_reason
  FROM `{dataset_id}.{table_name}` t
  CROSS JOIN duration_stats s
  WHERE {where_clause}
    AND t.duration_nano / 1000000 >= s.p95_ms
  ORDER BY t.duration_nano DESC
  LIMIT {limit // 2}
)
SELECT * FROM baseline_traces
UNION ALL
SELECT * FROM outlier_traces
ORDER BY selection_reason, duration_ms
"""
    else:
        return json.dumps(
            {"error": f"Unknown selection_strategy: {selection_strategy}"}
        )

    logger.info(f"Generated Exemplar Selection SQL ({selection_strategy}):\n{query.strip()}")

    return json.dumps(
        {
            "analysis_type": "exemplar_selection",
            "selection_strategy": selection_strategy,
            "sql_query": query.strip(),
            "description": f"Find {limit} exemplar traces using '{selection_strategy}' strategy",
            "next_steps": [
                "Execute this query using BigQuery MCP execute_sql tool",
                "Extract trace_id values from results",
                "Use fetch_trace to get full trace details",
                "Use run_triage_analysis to compare baseline vs outlier traces",
            ],
        }
    )


@adk_tool
def correlate_logs_with_trace(
    dataset_id: str,
    trace_id: str,
    trace_table_name: str = "_AllSpans",
    log_table_name: str = "_AllLogs",
    include_nearby_logs: bool = True,
    time_window_seconds: int = 30,
) -> str:
    """
    Finds logs correlated with a specific trace for root cause analysis.

    Args:
        dataset_id: BigQuery dataset ID
        trace_id: The trace ID to correlate logs with
        trace_table_name: Table name containing OTEL traces
        log_table_name: Table name containing OTEL logs
        include_nearby_logs: If True, include logs from same service around same time
        time_window_seconds: Time window for nearby logs

    Returns:
        JSON with SQL query to find correlated logs.
    """
    query = f"""
WITH trace_context AS (
  SELECT
    MIN(start_time) as trace_start,
    MAX(end_time) as trace_end,
    ANY_VALUE(JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name')) as service_name
  FROM `{dataset_id}.{trace_table_name}`
  WHERE trace_id = '{trace_id}'
    AND parent_span_id IS NULL
),
direct_logs AS (
  SELECT
    l.time_unix_nano as timestamp,
    l.severity_text as severity,
    l.body.string_value as message,
    JSON_EXTRACT_SCALAR(l.resource.attributes, '$.service.name') as service,
    'direct_correlation' as correlation_type,
    l.trace_id
  FROM `{dataset_id}.{log_table_name}` l
  WHERE l.trace_id = '{trace_id}'
)
"""

    if include_nearby_logs:
        query += f""",
nearby_logs AS (
  SELECT
    l.time_unix_nano as timestamp,
    l.severity_text as severity,
    l.body.string_value as message,
    JSON_EXTRACT_SCALAR(l.resource.attributes, '$.service.name') as service,
    'temporal_correlation' as correlation_type,
    l.trace_id
  FROM `{dataset_id}.{log_table_name}` l
  CROSS JOIN trace_context t
  WHERE JSON_EXTRACT_SCALAR(l.resource.attributes, '$.service.name') = t.service_name
    AND TIMESTAMP_MICROS(CAST(l.time_unix_nano / 1000 AS INT64)) >= TIMESTAMP_SUB(t.trace_start, INTERVAL {time_window_seconds} SECOND)
    AND TIMESTAMP_MICROS(CAST(l.time_unix_nano / 1000 AS INT64)) <= TIMESTAMP_ADD(t.trace_end, INTERVAL {time_window_seconds} SECOND)
    AND l.severity_text IN ('ERROR', 'ERROR2', 'ERROR3', 'ERROR4', 'FATAL', 'WARN')
    AND (l.trace_id IS NULL OR l.trace_id != '{trace_id}')
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

    logger.info(f"Generated Log Correlation SQL (trace={trace_id}):\n{query.strip()}")

    return json.dumps(
        {
            "analysis_type": "log_correlation",
            "trace_id": trace_id,
            "sql_query": query.strip(),
            "description": f"Find logs correlated with trace {trace_id}",
            "next_steps": [
                "Execute this query using BigQuery MCP execute_sql tool",
                "Look for ERROR or WARN severity logs",
                "Check log messages for exceptions, timeouts, or error codes",
            ],
        }
    )


@adk_tool
def compare_time_periods(
    dataset_id: str,
    table_name: str,
    baseline_hours_ago_start: int = 48,
    baseline_hours_ago_end: int = 24,
    anomaly_hours_ago_start: int = 24,
    anomaly_hours_ago_end: int = 0,
    service_name: str | None = None,
    operation_name: str | None = None,
) -> str:
    """
    Compares trace metrics between two time periods to detect degradations.

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
    """
    where_filter = ""
    if service_name:
        where_filter += f"AND JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') = '{service_name}'\n  "
    if operation_name:
        where_filter += f"AND name = '{operation_name}'\n  "

    query = f"""
WITH baseline_period AS (
  SELECT
    'baseline' as period,
    COUNT(*) as request_count,
    COUNTIF(status.code = 2) as error_count,
    ROUND(COUNTIF(status.code = 2) / COUNT(*) * 100, 2) as error_rate_pct,
    ROUND(APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(50)], 2) as p50_ms,
    ROUND(APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(95)], 2) as p95_ms,
    ROUND(APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(99)], 2) as p99_ms,
    ROUND(AVG(duration_nano / 1000000), 2) as avg_ms
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
    COUNTIF(status.code = 2) as error_count,
    ROUND(COUNTIF(status.code = 2) / COUNT(*) * 100, 2) as error_rate_pct,
    ROUND(APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(50)], 2) as p50_ms,
    ROUND(APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(95)], 2) as p95_ms,
    ROUND(APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(99)], 2) as p99_ms,
    ROUND(AVG(duration_nano / 1000000), 2) as avg_ms
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
  LAG(p95_ms) OVER (ORDER BY period) as baseline_p95_ms,
  p95_ms - LAG(p95_ms) OVER (ORDER BY period) as p95_delta_ms,
  ROUND((p95_ms - LAG(p95_ms) OVER (ORDER BY period)) / LAG(p95_ms) OVER (ORDER BY period) * 100, 1) as p95_change_pct,
  error_rate_pct - LAG(error_rate_pct) OVER (ORDER BY period) as error_rate_delta
FROM combined
ORDER BY period
"""

    logger.info(f"Generated Time Period Comparison SQL:\n{query.strip()}")

    return json.dumps(
        {
            "analysis_type": "time_period_comparison",
            "sql_query": query.strip(),
            "baseline_period": f"{baseline_hours_ago_start}h ago to {baseline_hours_ago_end}h ago",
            "anomaly_period": f"{anomaly_hours_ago_start}h ago to {anomaly_hours_ago_end}h ago",
            "description": "Compare metrics between baseline and anomaly time periods",
            "next_steps": [
                "Execute this query using BigQuery MCP execute_sql tool",
                "Look for significant deltas in p95_change_pct or error_rate_delta",
                "If degradation is confirmed, use find_exemplar_traces for each period",
            ],
        }
    )


@adk_tool
def detect_trend_changes(
    dataset_id: str,
    table_name: str,
    time_window_hours: int = 72,
    bucket_hours: int = 1,
    service_name: str | None = None,
    metric: str = "p95",
) -> str:
    """
    Detects when performance trends changed using time-series analysis.

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
        where_filter = f"AND JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') = '{service_name}'"

    if metric == "p95":
        metric_calc = "ROUND(APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(95)], 2) as metric_value"
        metric_name = "p95_latency_ms"
    elif metric == "p99":
        metric_calc = "ROUND(APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(99)], 2) as metric_value"
        metric_name = "p99_latency_ms"
    elif metric == "error_rate":
        metric_calc = "ROUND(COUNTIF(status.code = 2) / COUNT(*) * 100, 2) as metric_value"
        metric_name = "error_rate_pct"
    elif metric == "throughput":
        metric_calc = "COUNT(*) as metric_value"
        metric_name = "request_count"
    else:
        return json.dumps(
            {"error": f"Unknown metric: {metric}. Use p95, p99, error_rate, or throughput"}
        )

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
  HAVING sample_size >= 10
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
  CASE
    WHEN ABS(pct_change_1h) >= 20 THEN 'SIGNIFICANT_CHANGE'
    WHEN ABS(pct_change_1h) >= 10 THEN 'MODERATE_CHANGE'
    ELSE 'STABLE'
  END as change_magnitude
FROM with_moving_avg
ORDER BY time_bucket DESC
"""

    logger.info(f"Generated Trend Detection SQL ({metric}):\n{query.strip()}")

    return json.dumps(
        {
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
            ],
        }
    )
