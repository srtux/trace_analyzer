"""Cross-signal correlation tools for correlating traces, logs, and metrics.

This module implements the "holy grail" of observability: connecting the three
pillars (traces, logs, metrics) to provide a unified view of system behavior.

Key concepts:
- Exemplars: Trace references attached to metric data points (histogram buckets)
- Trace context: trace_id/span_id fields in log entries
- Temporal correlation: Aligning signals by time window

References:
- https://cloud.google.com/stackdriver/docs/instrumentation/advanced-topics/exemplars
- https://cloud.google.com/trace/docs/trace-log-integration
- https://opentelemetry.io/docs/concepts/signals/
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from ...common import adk_tool
from ...common.telemetry import get_tracer, get_meter

logger = logging.getLogger(__name__)

tracer = get_tracer(__name__)
meter = get_meter(__name__)

# Metrics for tracking correlation operations
correlation_operations = meter.create_counter(
    name="sre_agent.correlation.operations",
    description="Count of cross-signal correlation operations",
    unit="1",
)


@adk_tool
def correlate_trace_with_metrics(
    trace_id: str,
    dataset_id: str,
    trace_table_name: str = "_AllSpans",
    service_name: str | None = None,
    metrics_to_check: list[str] | None = None,
    time_buffer_seconds: int = 60,
) -> str:
    """
    Correlates a trace with relevant metrics during its execution window.

    This tool finds metrics that were recorded during the trace's execution,
    helping identify resource constraints, rate limits, or capacity issues
    that may have affected the request.

    Args:
        trace_id: The trace ID to correlate with metrics
        dataset_id: BigQuery dataset containing trace data
        trace_table_name: Table name containing OTel traces
        service_name: Optional service filter for targeted metric lookup
        metrics_to_check: Specific metric types to look for (default: common SRE metrics)
        time_buffer_seconds: Buffer before/after trace for metric correlation

    Returns:
        JSON with:
        - trace_time_window: Start/end of trace execution
        - recommended_metrics: PromQL queries to run for correlation
        - correlation_strategy: How to interpret the results
    """
    with tracer.start_as_current_span("correlate_trace_with_metrics") as span:
        span.set_attribute("trace_id", trace_id)
        correlation_operations.add(1, {"type": "trace_to_metrics"})

        # Default SRE-relevant metrics to check
        if metrics_to_check is None:
            metrics_to_check = [
                "http_request_duration_seconds",  # Request latency
                "http_requests_total",  # Request rate
                "process_cpu_seconds_total",  # CPU usage
                "process_resident_memory_bytes",  # Memory usage
                "grpc_server_handled_total",  # gRPC metrics
                "go_goroutines",  # Goroutine count (Go services)
                "jvm_memory_used_bytes",  # JVM memory (Java services)
                "db_client_connections",  # Database connections
                "redis_connected_clients",  # Redis connections
            ]

        # SQL to get trace time window and services involved
        trace_context_sql = f"""
WITH trace_spans AS (
  SELECT
    trace_id,
    span_id,
    parent_span_id,
    name as operation_name,
    JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') as service_name,
    JSON_EXTRACT_SCALAR(resource.attributes, '$.host.name') as host_name,
    start_time,
    end_time,
    TIMESTAMP_DIFF(end_time, start_time, MILLISECOND) as duration_ms,
    status.code as status_code,
    kind as span_kind
  FROM `{dataset_id}.{trace_table_name}`
  WHERE trace_id = '{trace_id}'
)
SELECT
  MIN(start_time) as trace_start,
  MAX(end_time) as trace_end,
  TIMESTAMP_DIFF(MAX(end_time), MIN(start_time), MILLISECOND) as total_duration_ms,
  ARRAY_AGG(DISTINCT service_name IGNORE NULLS) as services_involved,
  ARRAY_AGG(DISTINCT host_name IGNORE NULLS) as hosts_involved,
  COUNT(*) as span_count,
  COUNTIF(status_code = 2) as error_span_count,
  ARRAY_AGG(
    STRUCT(
      service_name,
      operation_name,
      duration_ms,
      status_code
    )
    ORDER BY duration_ms DESC
    LIMIT 5
  ) as slowest_spans
FROM trace_spans
"""

        # Generate PromQL queries for each metric type
        promql_queries = []
        service_filter = f'service="{service_name}"' if service_name else ""

        for metric in metrics_to_check:
            # Request latency histogram (with exemplars!)
            if "duration" in metric or "latency" in metric:
                promql_queries.append({
                    "metric": metric,
                    "query": f'histogram_quantile(0.95, sum(rate({metric}_bucket{{{service_filter}}}[5m])) by (le, service))',
                    "purpose": "Check P95 latency during trace execution",
                    "exemplar_query": f'{metric}_bucket{{{service_filter}}}',
                    "has_exemplars": True,
                })
            # Counter metrics (request rate, errors)
            elif "total" in metric:
                promql_queries.append({
                    "metric": metric,
                    "query": f'sum(rate({metric}{{{service_filter}}}[1m])) by (service, code)',
                    "purpose": "Check request/error rate during trace execution",
                    "has_exemplars": False,
                })
            # Gauge metrics (CPU, memory, connections)
            else:
                promql_queries.append({
                    "metric": metric,
                    "query": f'{metric}{{{service_filter}}}',
                    "purpose": "Check resource utilization during trace execution",
                    "has_exemplars": False,
                })

        result = {
            "analysis_type": "trace_metrics_correlation",
            "trace_id": trace_id,
            "trace_context_sql": trace_context_sql.strip(),
            "recommended_promql_queries": promql_queries,
            "time_buffer_seconds": time_buffer_seconds,
            "correlation_strategy": {
                "step_1": "Execute trace_context_sql to get trace time window and services",
                "step_2": "Use trace start/end times (with buffer) as PromQL time range",
                "step_3": "Run recommended PromQL queries for each service involved",
                "step_4": "For histogram metrics, check exemplars to find traces with similar latency",
                "step_5": "Look for resource anomalies (CPU spikes, memory pressure, connection exhaustion)",
            },
            "exemplar_usage": {
                "description": "Exemplars link metric data points to specific traces",
                "how_to_use": "Query histogram buckets and check for exemplar annotations",
                "gcp_ui": "In Cloud Monitoring, hover over histogram data points to see linked traces",
            },
            "next_steps": [
                "Execute trace_context_sql using BigQuery MCP",
                "Run PromQL queries using mcp_query_range with trace time window",
                "Compare metric values against baseline to detect anomalies",
                "Check exemplars on latency histograms to find related traces",
            ],
        }

        logger.info(f"Generated trace-metrics correlation for trace {trace_id}")
        return json.dumps(result)


@adk_tool
def correlate_metrics_with_traces_via_exemplars(
    dataset_id: str,
    metric_name: str,
    service_name: str,
    percentile_threshold: float = 95.0,
    time_window_hours: int = 1,
    trace_table_name: str = "_AllSpans",
) -> str:
    """
    Uses exemplar-style analysis to find traces corresponding to metric outliers.

    Exemplars are trace references attached to histogram bucket data points.
    This tool simulates exemplar lookup by finding traces that match the
    latency characteristics of metric outliers.

    In GCP Managed Prometheus with OpenTelemetry:
    - Exemplars are automatically attached when metrics are recorded within a span
    - They appear as annotations on histogram data points in Cloud Monitoring UI
    - You can click an exemplar to jump directly to the corresponding trace

    Args:
        dataset_id: BigQuery dataset containing trace data
        metric_name: The histogram metric to analyze (e.g., http_request_duration_seconds)
        service_name: Service to filter by
        percentile_threshold: Find traces above this percentile (default: 95th)
        time_window_hours: How far back to search
        trace_table_name: Table name containing OTel traces

    Returns:
        JSON with SQL to find exemplar-like traces and PromQL for histogram analysis
    """
    with tracer.start_as_current_span("correlate_metrics_with_traces_via_exemplars") as span:
        span.set_attribute("metric_name", metric_name)
        span.set_attribute("service_name", service_name)
        correlation_operations.add(1, {"type": "exemplar_correlation"})

        percentile_offset = int(percentile_threshold)

        # SQL to find traces matching the latency distribution outliers
        exemplar_sql = f"""
-- Find traces that would be exemplars for high-latency histogram buckets
-- These are traces above P{percentile_offset} that represent metric outliers
WITH latency_distribution AS (
  SELECT
    trace_id,
    span_id,
    name as operation_name,
    JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') as service_name,
    start_time,
    duration_nano / 1000000 as duration_ms,
    status.code as status_code,
    -- Calculate percentile ranking
    PERCENT_RANK() OVER (
      PARTITION BY JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name')
      ORDER BY duration_nano
    ) * 100 as percentile_rank
  FROM `{dataset_id}.{trace_table_name}`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)
    AND parent_span_id IS NULL  -- Root spans only
    AND JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') = '{service_name}'
    AND kind = 2  -- SERVER spans (incoming requests)
),
-- Calculate histogram bucket boundaries (like Prometheus buckets)
histogram_buckets AS (
  SELECT
    service_name,
    -- Common histogram bucket boundaries (ms)
    COUNTIF(duration_ms <= 10) as bucket_10ms,
    COUNTIF(duration_ms <= 25) as bucket_25ms,
    COUNTIF(duration_ms <= 50) as bucket_50ms,
    COUNTIF(duration_ms <= 100) as bucket_100ms,
    COUNTIF(duration_ms <= 250) as bucket_250ms,
    COUNTIF(duration_ms <= 500) as bucket_500ms,
    COUNTIF(duration_ms <= 1000) as bucket_1s,
    COUNTIF(duration_ms <= 2500) as bucket_2_5s,
    COUNTIF(duration_ms <= 5000) as bucket_5s,
    COUNTIF(duration_ms <= 10000) as bucket_10s,
    COUNT(*) as bucket_inf,
    -- Latency statistics
    APPROX_QUANTILES(duration_ms, 100)[OFFSET(50)] as p50_ms,
    APPROX_QUANTILES(duration_ms, 100)[OFFSET(95)] as p95_ms,
    APPROX_QUANTILES(duration_ms, 100)[OFFSET(99)] as p99_ms
  FROM latency_distribution
  GROUP BY service_name
),
-- Select exemplar candidates (traces above threshold)
exemplar_candidates AS (
  SELECT
    l.trace_id,
    l.operation_name,
    l.duration_ms,
    l.percentile_rank,
    l.start_time,
    l.status_code,
    h.p95_ms,
    h.p99_ms,
    -- Determine which histogram bucket this trace falls into
    CASE
      WHEN l.duration_ms <= 10 THEN '10ms'
      WHEN l.duration_ms <= 25 THEN '25ms'
      WHEN l.duration_ms <= 50 THEN '50ms'
      WHEN l.duration_ms <= 100 THEN '100ms'
      WHEN l.duration_ms <= 250 THEN '250ms'
      WHEN l.duration_ms <= 500 THEN '500ms'
      WHEN l.duration_ms <= 1000 THEN '1s'
      WHEN l.duration_ms <= 2500 THEN '2.5s'
      WHEN l.duration_ms <= 5000 THEN '5s'
      WHEN l.duration_ms <= 10000 THEN '10s'
      ELSE '+Inf'
    END as histogram_bucket,
    'exemplar_candidate' as selection_reason
  FROM latency_distribution l
  CROSS JOIN histogram_buckets h
  WHERE l.percentile_rank >= {percentile_threshold}
  ORDER BY l.duration_ms DESC
  LIMIT 20
)
SELECT * FROM exemplar_candidates
ORDER BY duration_ms DESC
"""

        # PromQL queries for histogram analysis
        promql_queries = {
            "histogram_quantile_p95": f'histogram_quantile(0.95, sum(rate({metric_name}_bucket{{service="{service_name}"}}[5m])) by (le))',
            "histogram_quantile_p99": f'histogram_quantile(0.99, sum(rate({metric_name}_bucket{{service="{service_name}"}}[5m])) by (le))',
            "request_rate": f'sum(rate({metric_name}_count{{service="{service_name}"}}[1m]))',
            "bucket_distribution": f'{metric_name}_bucket{{service="{service_name}"}}',
        }

        result = {
            "analysis_type": "exemplar_correlation",
            "metric_name": metric_name,
            "service_name": service_name,
            "percentile_threshold": percentile_threshold,
            "exemplar_sql": exemplar_sql.strip(),
            "promql_queries": promql_queries,
            "explanation": {
                "what_are_exemplars": (
                    "Exemplars are sample trace references attached to histogram metric data points. "
                    "They let you jump from a metric spike directly to a representative trace."
                ),
                "how_this_helps": (
                    "When you see P95 latency spike in metrics, exemplars show you WHICH specific "
                    "requests were slow, with full distributed trace context."
                ),
                "gcp_implementation": (
                    "GCP Managed Prometheus automatically collects exemplars from OpenTelemetry SDKs. "
                    "In Cloud Monitoring UI, hover over histogram data points to see linked traces."
                ),
            },
            "workflow": [
                "1. Run the exemplar_sql to find traces matching your latency threshold",
                "2. Use the PromQL queries to see the metric distribution",
                "3. Compare trace timing with metric spike timing",
                "4. Fetch the exemplar trace IDs for detailed analysis with fetch_trace",
            ],
            "next_steps": [
                "Execute exemplar_sql using BigQuery MCP execute_sql",
                "Run PromQL queries with mcp_query_range",
                "Use fetch_trace on the returned trace_ids for detailed span analysis",
                "Run correlate_logs_with_trace to get log context",
            ],
        }

        logger.info(f"Generated exemplar correlation for {metric_name} on {service_name}")
        return json.dumps(result)


@adk_tool
def build_cross_signal_timeline(
    trace_id: str,
    dataset_id: str,
    trace_table_name: str = "_AllSpans",
    log_table_name: str = "_AllLogs",
    time_buffer_seconds: int = 30,
) -> str:
    """
    Builds a unified timeline correlating traces, logs, and metrics events.

    This is the "unified view" of observability - aligning all three pillars
    on a single timeline to understand the sequence of events during an incident.

    Args:
        trace_id: The trace ID to build timeline around
        dataset_id: BigQuery dataset containing telemetry data
        trace_table_name: Table name containing OTel traces
        log_table_name: Table name containing OTel logs
        time_buffer_seconds: Buffer before/after trace for log correlation

    Returns:
        JSON with SQL for unified timeline and interpretation guide
    """
    with tracer.start_as_current_span("build_cross_signal_timeline") as span:
        span.set_attribute("trace_id", trace_id)
        correlation_operations.add(1, {"type": "timeline_correlation"})

        timeline_sql = f"""
-- Build a unified timeline of trace spans and correlated logs
-- This shows the sequence of events during request processing

WITH trace_spans AS (
  SELECT
    'SPAN' as event_type,
    start_time as event_time,
    end_time,
    trace_id,
    span_id,
    parent_span_id,
    name as event_name,
    JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') as service_name,
    CASE status.code
      WHEN 0 THEN 'UNSET'
      WHEN 1 THEN 'OK'
      WHEN 2 THEN 'ERROR'
      ELSE 'UNKNOWN'
    END as status,
    ROUND(duration_nano / 1000000, 2) as duration_ms,
    CASE kind
      WHEN 1 THEN 'INTERNAL'
      WHEN 2 THEN 'SERVER'
      WHEN 3 THEN 'CLIENT'
      WHEN 4 THEN 'PRODUCER'
      WHEN 5 THEN 'CONSUMER'
      ELSE 'UNKNOWN'
    END as span_kind,
    -- Extract key attributes for context
    JSON_EXTRACT_SCALAR(attributes, '$.http.method') as http_method,
    JSON_EXTRACT_SCALAR(attributes, '$.http.url') as http_url,
    JSON_EXTRACT_SCALAR(attributes, '$.http.status_code') as http_status,
    JSON_EXTRACT_SCALAR(attributes, '$.db.system') as db_system,
    JSON_EXTRACT_SCALAR(attributes, '$.db.statement') as db_statement
  FROM `{dataset_id}.{trace_table_name}`
  WHERE trace_id = '{trace_id}'
),
trace_time_bounds AS (
  SELECT
    MIN(start_time) as trace_start,
    MAX(end_time) as trace_end,
    ARRAY_AGG(DISTINCT service_name IGNORE NULLS) as trace_services
  FROM trace_spans
),
-- Logs directly correlated via trace_id
direct_logs AS (
  SELECT
    'LOG_DIRECT' as event_type,
    TIMESTAMP_MICROS(CAST(time_unix_nano / 1000 AS INT64)) as event_time,
    NULL as end_time,
    trace_id,
    span_id,
    NULL as parent_span_id,
    CONCAT('[', severity_text, '] ', COALESCE(body.string_value, '')) as event_name,
    JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') as service_name,
    severity_text as status,
    NULL as duration_ms,
    'LOG' as span_kind,
    NULL as http_method,
    NULL as http_url,
    NULL as http_status,
    NULL as db_system,
    NULL as db_statement
  FROM `{dataset_id}.{log_table_name}`
  WHERE trace_id = '{trace_id}'
),
-- Logs temporally correlated (same service, same time window)
temporal_logs AS (
  SELECT
    'LOG_TEMPORAL' as event_type,
    TIMESTAMP_MICROS(CAST(l.time_unix_nano / 1000 AS INT64)) as event_time,
    NULL as end_time,
    l.trace_id,
    l.span_id,
    NULL as parent_span_id,
    CONCAT('[', l.severity_text, '] ', COALESCE(l.body.string_value, '')) as event_name,
    JSON_EXTRACT_SCALAR(l.resource.attributes, '$.service.name') as service_name,
    l.severity_text as status,
    NULL as duration_ms,
    'LOG' as span_kind,
    NULL as http_method,
    NULL as http_url,
    NULL as http_status,
    NULL as db_system,
    NULL as db_statement
  FROM `{dataset_id}.{log_table_name}` l
  CROSS JOIN trace_time_bounds t
  WHERE JSON_EXTRACT_SCALAR(l.resource.attributes, '$.service.name') IN UNNEST(t.trace_services)
    AND TIMESTAMP_MICROS(CAST(l.time_unix_nano / 1000 AS INT64))
        BETWEEN TIMESTAMP_SUB(t.trace_start, INTERVAL {time_buffer_seconds} SECOND)
            AND TIMESTAMP_ADD(t.trace_end, INTERVAL {time_buffer_seconds} SECOND)
    AND l.severity_text IN ('ERROR', 'WARN', 'FATAL', 'CRITICAL')
    AND (l.trace_id IS NULL OR l.trace_id != '{trace_id}')
  LIMIT 50
),
-- Combine all events into timeline
unified_timeline AS (
  SELECT * FROM trace_spans
  UNION ALL
  SELECT * FROM direct_logs
  UNION ALL
  SELECT * FROM temporal_logs
)
SELECT
  event_type,
  event_time,
  end_time,
  trace_id,
  span_id,
  parent_span_id,
  event_name,
  service_name,
  status,
  duration_ms,
  span_kind,
  http_method,
  http_url,
  http_status,
  db_system,
  db_statement,
  -- Time relative to trace start for easy reading
  TIMESTAMP_DIFF(event_time, (SELECT MIN(event_time) FROM unified_timeline WHERE event_type = 'SPAN'), MILLISECOND) as relative_time_ms
FROM unified_timeline
ORDER BY event_time
"""

        result = {
            "analysis_type": "cross_signal_timeline",
            "trace_id": trace_id,
            "timeline_sql": timeline_sql.strip(),
            "event_types": {
                "SPAN": "Trace span (start of operation)",
                "LOG_DIRECT": "Log entry with matching trace_id (direct correlation)",
                "LOG_TEMPORAL": "Log entry from same service/time (temporal correlation)",
            },
            "correlation_fields": {
                "trace_id": "Unique identifier for the distributed trace",
                "span_id": "Identifier for specific operation within trace",
                "service_name": "Which service emitted the event",
                "relative_time_ms": "Milliseconds since trace started",
            },
            "how_to_read": {
                "step_1": "Look at the relative_time_ms column to understand event ordering",
                "step_2": "LOG_DIRECT events are definitively part of this trace",
                "step_3": "LOG_TEMPORAL events happened during trace but may be from other requests",
                "step_4": "ERROR/WARN logs often indicate the root cause",
                "step_5": "Check db_system/db_statement for slow database calls",
            },
            "next_steps": [
                "Execute timeline_sql using BigQuery MCP execute_sql",
                "Sort by relative_time_ms to see chronological order",
                "Look for ERROR status spans or logs",
                "Check if errors cascade through services",
            ],
        }

        logger.info(f"Generated cross-signal timeline for trace {trace_id}")
        return json.dumps(result)


@adk_tool
def analyze_signal_correlation_strength(
    dataset_id: str,
    trace_table_name: str = "_AllSpans",
    log_table_name: str = "_AllLogs",
    service_name: str | None = None,
    time_window_hours: int = 24,
) -> str:
    """
    Analyzes how well traces, logs, and metrics are correlated in the system.

    This diagnostic tool helps identify gaps in observability instrumentation:
    - Are logs properly annotated with trace context?
    - Are metrics being recorded with exemplars?
    - Which services have good vs poor correlation?

    Args:
        dataset_id: BigQuery dataset containing telemetry data
        trace_table_name: Table name containing OTel traces
        log_table_name: Table name containing OTel logs
        service_name: Optional service to focus on
        time_window_hours: Time window for analysis

    Returns:
        JSON with correlation health metrics and improvement recommendations
    """
    with tracer.start_as_current_span("analyze_signal_correlation_strength") as span:
        correlation_operations.add(1, {"type": "correlation_health"})

        service_filter = ""
        if service_name:
            service_filter = f"AND JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') = '{service_name}'"

        correlation_sql = f"""
-- Analyze cross-signal correlation strength across the system
-- This helps identify instrumentation gaps

WITH trace_stats AS (
  SELECT
    JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') as service_name,
    COUNT(DISTINCT trace_id) as total_traces,
    COUNT(*) as total_spans,
    COUNTIF(status.code = 2) as error_spans,
    -- Check for span events (logs attached to spans)
    COUNTIF(ARRAY_LENGTH(events) > 0) as spans_with_events,
    -- Check for span links (cross-trace correlation)
    COUNTIF(ARRAY_LENGTH(links) > 0) as spans_with_links
  FROM `{dataset_id}.{trace_table_name}`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)
    {service_filter}
  GROUP BY service_name
),
log_stats AS (
  SELECT
    JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') as service_name,
    COUNT(*) as total_logs,
    COUNTIF(trace_id IS NOT NULL) as logs_with_trace_id,
    COUNTIF(span_id IS NOT NULL) as logs_with_span_id,
    COUNTIF(severity_text IN ('ERROR', 'FATAL', 'CRITICAL')) as error_logs,
    -- Check if error logs have trace context
    COUNTIF(severity_text IN ('ERROR', 'FATAL', 'CRITICAL') AND trace_id IS NOT NULL) as error_logs_with_trace
  FROM `{dataset_id}.{log_table_name}`
  WHERE time_unix_nano >= UNIX_MICROS(TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)) * 1000
    {service_filter}
  GROUP BY service_name
),
correlation_metrics AS (
  SELECT
    COALESCE(t.service_name, l.service_name) as service_name,
    t.total_traces,
    t.total_spans,
    t.error_spans,
    t.spans_with_events,
    t.spans_with_links,
    l.total_logs,
    l.logs_with_trace_id,
    l.logs_with_span_id,
    l.error_logs,
    l.error_logs_with_trace,
    -- Calculate correlation scores (0-100%)
    ROUND(SAFE_DIVIDE(l.logs_with_trace_id, l.total_logs) * 100, 1) as log_trace_correlation_pct,
    ROUND(SAFE_DIVIDE(l.error_logs_with_trace, l.error_logs) * 100, 1) as error_log_trace_correlation_pct,
    ROUND(SAFE_DIVIDE(t.spans_with_events, t.total_spans) * 100, 1) as span_events_coverage_pct,
    ROUND(SAFE_DIVIDE(t.spans_with_links, t.total_spans) * 100, 1) as span_links_coverage_pct
  FROM trace_stats t
  FULL OUTER JOIN log_stats l ON t.service_name = l.service_name
)
SELECT
  service_name,
  total_traces,
  total_spans,
  error_spans,
  total_logs,
  logs_with_trace_id,
  error_logs,
  error_logs_with_trace,
  log_trace_correlation_pct,
  error_log_trace_correlation_pct,
  span_events_coverage_pct,
  span_links_coverage_pct,
  -- Overall correlation health score
  ROUND(
    (COALESCE(log_trace_correlation_pct, 0) * 0.4 +
     COALESCE(error_log_trace_correlation_pct, 0) * 0.4 +
     COALESCE(span_events_coverage_pct, 0) * 0.1 +
     COALESCE(span_links_coverage_pct, 0) * 0.1),
    1
  ) as overall_correlation_score,
  -- Recommendations based on gaps
  CASE
    WHEN COALESCE(log_trace_correlation_pct, 0) < 50 THEN 'LOW: Add trace context to logging framework'
    WHEN COALESCE(log_trace_correlation_pct, 0) < 80 THEN 'MEDIUM: Improve log instrumentation coverage'
    ELSE 'GOOD: Log-trace correlation is healthy'
  END as log_correlation_status
FROM correlation_metrics
WHERE service_name IS NOT NULL
ORDER BY overall_correlation_score
"""

        result = {
            "analysis_type": "correlation_strength",
            "correlation_sql": correlation_sql.strip(),
            "metrics_explained": {
                "log_trace_correlation_pct": "% of logs with trace_id (target: >80%)",
                "error_log_trace_correlation_pct": "% of ERROR logs with trace_id (target: 100%)",
                "span_events_coverage_pct": "% of spans with embedded log events",
                "span_links_coverage_pct": "% of spans with cross-trace links",
                "overall_correlation_score": "Weighted score of all correlation metrics",
            },
            "score_interpretation": {
                "90-100": "Excellent: Full cross-signal correlation",
                "70-89": "Good: Most signals are correlated",
                "50-69": "Fair: Significant correlation gaps exist",
                "0-49": "Poor: Limited cross-signal debugging capability",
            },
            "improvement_recommendations": {
                "low_log_correlation": [
                    "Configure OpenTelemetry logging SDK to inject trace context",
                    "Use logging.googleapis.com/trace and logging.googleapis.com/spanId fields",
                    "Ensure log statements are called within active spans",
                ],
                "low_error_correlation": [
                    "Add try/catch blocks that log with span context",
                    "Use span.record_exception() for error handling",
                    "Ensure error handlers have access to trace context",
                ],
                "low_span_events": [
                    "Use span.add_event() for important checkpoints",
                    "Consider adding business events to spans",
                ],
                "low_span_links": [
                    "Use span links for async/batch processing",
                    "Link cause traces to effect traces",
                ],
            },
            "next_steps": [
                "Execute correlation_sql using BigQuery MCP execute_sql",
                "Identify services with low correlation scores",
                "Prioritize improving error_log_trace_correlation",
                "Focus on services involved in recent incidents",
            ],
        }

        logger.info("Generated signal correlation strength analysis")
        return json.dumps(result)
