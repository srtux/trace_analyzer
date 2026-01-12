"""Pre-defined BigQuery SQL queries for SRE Agent analysis."""


def get_aggregate_metrics_query(table_name: str, start_time: str, end_time: str) -> str:
    """Get query for service-level aggregate metrics.

    Args:
        table_name: Fully qualified table name (e.g. proj.dataset._AllSpans).
        start_time: ISO timestamp.
        end_time: ISO timestamp.
    """
    # Assuming attributes.key='service.name' or similar OTel convention.
    # We unnest attributes to find service name.

    return f"""
    WITH Spans AS (
      SELECT
        span_id,
        trace_id,
        parent_span_id,
        start_time,
        end_time,
        TIMESTAMP_DIFF(end_time, start_time, MILLISECOND) as duration_ms,
        (SELECT value.string_value FROM UNNEST(attributes) WHERE key = 'service.name') as service_name,
        (SELECT value.int_value FROM UNNEST(status) WHERE key = 'code') as status_code # Check OTel status schema.  Actually OTel status is often a struct.
      FROM `{table_name}`
      WHERE start_time BETWEEN TIMESTAMP('{start_time}') AND TIMESTAMP('{end_time}')
    )
    SELECT
      service_name,
      COUNT(*) as request_count,
      AVG(duration_ms) as avg_latency,
      APPROX_QUANTILES(duration_ms, 100)[OFFSET(50)] as p50_latency,
      APPROX_QUANTILES(duration_ms, 100)[OFFSET(95)] as p95_latency,
      APPROX_QUANTILES(duration_ms, 100)[OFFSET(99)] as p99_latency,
      COUNTIF(status_code = 2) as error_count # OTel status: 0=Unset, 1=Ok, 2=Error
    FROM Spans
    WHERE service_name IS NOT NULL
    GROUP BY service_name
    ORDER BY request_count DESC
    """


def get_baseline_traces_query(
    table_name: str, service_name: str, start_time: str, end_time: str, limit: int = 10
) -> str:
    """Get baseline (p50) traces for a service."""
    return f"""
    WITH Spans AS (
      SELECT
        trace_id,
        TIMESTAMP_DIFF(end_time, start_time, MILLISECOND) as duration_ms,
        (SELECT value.string_value FROM UNNEST(attributes) WHERE key = 'service.name') as service_name
      FROM `{table_name}`
      WHERE start_time BETWEEN TIMESTAMP('{start_time}') AND TIMESTAMP('{end_time}')
      AND parent_span_id IS NULL -- Only root spans define trace duration typically
    )
    SELECT trace_id
    FROM Spans
    WHERE service_name = '{service_name}'
    -- Filter for traces near p50 (naive approach: order by ABS(duration - p50))
    QUALIFY ROW_NUMBER() OVER (ORDER BY ABS(duration_ms - (SELECT PERCENTILE_CONT(duration_ms, 0.5) OVER()))) <= {limit}
    """


def get_anomaly_traces_query(
    table_name: str, service_name: str, start_time: str, end_time: str, limit: int = 10
) -> str:
    """Get anomaly (p99 or error) traces for a service."""
    return f"""
    WITH Spans AS (
      SELECT
        trace_id,
        TIMESTAMP_DIFF(end_time, start_time, MILLISECOND) as duration_ms,
        (SELECT value.string_value FROM UNNEST(attributes) WHERE key = 'service.name') as service_name,
        (SELECT value.int_value FROM UNNEST(status) WHERE key = 'code') as status_code
      FROM `{table_name}`
      WHERE start_time BETWEEN TIMESTAMP('{start_time}') AND TIMESTAMP('{end_time}')
      AND parent_span_id IS NULL
    )
    SELECT trace_id
    FROM Spans
    WHERE service_name = '{service_name}'
    AND (
        duration_ms >= (SELECT PERCENTILE_CONT(duration_ms, 0.99) OVER())
        OR status_code = 2
    )
    LIMIT {limit}
    """
