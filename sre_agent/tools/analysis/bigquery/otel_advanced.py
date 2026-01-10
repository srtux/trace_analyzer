"""Advanced BigQuery-powered tools for OpenTelemetry data analysis.

This module provides specialized analysis queries for span events, links,
exceptions, and specific diagnostic scenarios (HTTP, DB, etc.).
"""

import json
import logging

from ...common import adk_tool

logger = logging.getLogger(__name__)


@adk_tool
def analyze_span_events(
    dataset_id: str,
    table_name: str = "_AllSpans",
    time_window_hours: int = 24,
    event_name_filter: str | None = None,
    service_name: str | None = None,
) -> str:
    """
    Analyzes span events (e.g., logs, exceptions attached to spans).

    Args:
        dataset_id: BigQuery dataset ID
        table_name: Table name
        time_window_hours: Time window in hours
        event_name_filter: Optional filter for event name
        service_name: Optional filter for service name

    Returns:
        JSON with SQL query.
    """
    where_conditions = [
        f"start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)",
        "ARRAY_LENGTH(events) > 0",
    ]
    if service_name:
        where_conditions.append(
            f"JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') = '{service_name}'"
        )

    # If we filter by event name, we put it in the UNNEST check or outside
    # Usually easier to filter after UNNEST

    where_clause = " AND ".join(where_conditions)
    event_filter_clause = (
        f"AND event.name = '{event_name_filter}'" if event_name_filter else ""
    )

    query = f"""
SELECT
  t.trace_id,
  t.span_id,
  JSON_EXTRACT_SCALAR(t.resource.attributes, '$.service.name') as service_name,
  event.name,
  event.time,
  JSON_EXTRACT_SCALAR(event.attributes, '$.exception.type') as `exception.type`,
  JSON_EXTRACT_SCALAR(event.attributes, '$.exception.message') as `exception.message`,
  JSON_EXTRACT_SCALAR(event.attributes, '$.exception.stacktrace') as `exception.stacktrace`
FROM `{dataset_id}.{table_name}` t,
UNNEST(events) as event
WHERE {where_clause}
  {event_filter_clause}
ORDER BY event.time DESC
LIMIT 100
"""
    return json.dumps(
        {
            "analysis_type": "span_events",
            "sql_query": query.strip(),
            "description": "Analyze span events from OpenTelemetry data",
        }
    )


@adk_tool
def analyze_exception_patterns(
    dataset_id: str,
    table_name: str = "_AllSpans",
    time_window_hours: int = 24,
    group_by: str = "exception_type",
) -> str:
    """
    Analyzes patterns in exceptions found in span events.

    Args:
        dataset_id: BigQuery dataset
        table_name: Table name
        time_window_hours: Time window
        group_by: 'exception_type' or 'service_name'
    """
    group_expr = "JSON_EXTRACT_SCALAR(event.attributes, '$.exception.type')"
    group_alias = "exception_type"

    if group_by == "service_name":
        group_expr = "JSON_EXTRACT_SCALAR(t.resource.attributes, '$.service.name')"
        group_alias = "service_name"

    query = f"""
SELECT
  {group_expr} as {group_alias},
  COUNT(*) as exception_count,
  COUNT(DISTINCT t.trace_id) as affected_traces,
  COUNT(DISTINCT JSON_EXTRACT_SCALAR(t.resource.attributes, '$.service.name')) as affected_services,
  STRING_AGG(DISTINCT JSON_EXTRACT_SCALAR(event.attributes, '$.exception.message') LIMIT 5) as sample_messages
FROM `{dataset_id}.{table_name}` t,
UNNEST(events) as event
WHERE t.start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)
  AND event.name = 'exception'
GROUP BY 1
ORDER BY exception_count DESC
LIMIT 50
"""
    return json.dumps(
        {
            "analysis_type": "exception_patterns",
            "sql_query": query.strip(),
            "description": "Analyze exception patterns",
        }
    )


@adk_tool
def analyze_span_links(
    dataset_id: str,
    table_name: str = "_AllSpans",
    time_window_hours: int = 24,
    service_name: str | None = None,
) -> str:
    """
    Analyzes span links which connect causal traces.
    """
    where_conditions = [
        f"start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)",
        "ARRAY_LENGTH(links) > 0",
    ]
    if service_name:
        where_conditions.append(
            f"JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') = '{service_name}'"
        )

    where_clause = " AND ".join(where_conditions)

    query = f"""
SELECT
  t.trace_id,
  t.span_id,
  JSON_EXTRACT_SCALAR(t.resource.attributes, '$.service.name') as service_name,
  link.trace_id as `link.trace_id`,
  link.span_id as `link.span_id`,
  JSON_EXTRACT_SCALAR(link.attributes, '$.type') as `link.type`,
  JSON_EXTRACT_SCALAR(link.attributes, '$.reason') as `link.reason`,
  TO_JSON_STRING(link.attributes) as `link.attributes`
FROM `{dataset_id}.{table_name}` t,
UNNEST(links) as link
WHERE {where_clause}
LIMIT 100
"""
    return json.dumps(
        {
            "analysis_type": "span_links",
            "sql_query": query.strip(),
            "description": "Analyze span links",
        }
    )


@adk_tool
def analyze_link_patterns(
    dataset_id: str,
    table_name: str = "_AllSpans",
    time_window_hours: int = 24,
) -> str:
    """
    Analyzes high-level statistics about span links.
    """
    query = f"""
SELECT
  JSON_EXTRACT_SCALAR(t.resource.attributes, '$.service.name') as service_name,
  COUNTIF(ARRAY_LENGTH(links) > 0) as spans_with_links,
  SUM(ARRAY_LENGTH(links)) as total_links,
  ROUND(AVG(ARRAY_LENGTH(links)), 2) as avg_links_per_span
FROM `{dataset_id}.{table_name}` t
WHERE t.start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)
GROUP BY 1
ORDER BY total_links DESC
"""
    return json.dumps(
        {
            "analysis_type": "link_patterns",
            "sql_query": query.strip(),
            "description": "Analyze link patterns",
        }
    )


@adk_tool
def analyze_instrumentation_libraries(
    dataset_id: str,
    table_name: str = "_AllSpans",
    time_window_hours: int = 24,
) -> str:
    """
    Analyzes usage of instrumentation libraries/scopes.
    """
    query = f"""
SELECT
  instrumentation_scope.name as `instrumentation_scope.name`,
  instrumentation_scope.version as `instrumentation_scope.version`,
  instrumentation_scope.schema_url as `instrumentation_scope.schema_url`,
  COUNT(*) as span_count,
  COUNT(DISTINCT JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name')) as service_count,
  COUNT(DISTINCT trace_id) as trace_count,
  STRING_AGG(DISTINCT JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') LIMIT 5) as services_using
FROM `{dataset_id}.{table_name}`
WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)
GROUP BY 1, 2, 3
ORDER BY span_count DESC
"""
    return json.dumps(
        {
            "analysis_type": "instrumentation_libraries",
            "sql_query": query.strip(),
            "description": "Analyze instrumentation libraries",
        }
    )


@adk_tool
def analyze_http_attributes(
    dataset_id: str,
    table_name: str = "_AllSpans",
    time_window_hours: int = 24,
    min_request_count: int = 1,
) -> str:
    """
    Analyzes HTTP semantic conventions (SERVER spans).
    """
    query = f"""
SELECT
  JSON_EXTRACT_SCALAR(attributes, '$.http.method') as `http.method`,
  JSON_EXTRACT_SCALAR(attributes, '$.http.target') as `http.target`,
  JSON_EXTRACT_SCALAR(attributes, '$.http.status_code') as `http.status_code`,
  COUNT(*) as request_count,
  ROUND(APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(50)], 2) as p50_ms,
  ROUND(APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(95)], 2) as p95_ms,
  ROUND(APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(99)], 2) as p99_ms,
  AVG(CAST(JSON_EXTRACT_SCALAR(attributes, '$.http.request_content_length') AS INT64)) as `http.request_content_length`,
  AVG(CAST(JSON_EXTRACT_SCALAR(attributes, '$.http.response_content_length') AS INT64)) as `http.response_content_length`
FROM `{dataset_id}.{table_name}`
WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)
  AND kind = 2 -- SERVER
GROUP BY 1, 2, 3
HAVING request_count >= {min_request_count}
ORDER BY request_count DESC
"""
    return json.dumps(
        {
            "analysis_type": "http_attributes",
            "sql_query": query.strip(),
            "description": "Analyze HTTP attributes",
        }
    )


@adk_tool
def analyze_database_operations(
    dataset_id: str,
    table_name: str = "_AllSpans",
    time_window_hours: int = 24,
    db_system: str | None = None,
) -> str:
    """
    Analyzes Database semantic conventions (CLIENT spans).
    """
    where_extra = ""
    if db_system:
        where_extra = (
            f"AND JSON_EXTRACT_SCALAR(attributes, '$.db.system') = '{db_system}'"
        )

    query = f"""
SELECT
  JSON_EXTRACT_SCALAR(attributes, '$.db.system') as `db.system`,
  JSON_EXTRACT_SCALAR(attributes, '$.db.name') as `db.name`,
  JSON_EXTRACT_SCALAR(attributes, '$.db.operation') as `db.operation`,
  COUNT(*) as call_count,
  ROUND(AVG(duration_nano / 1000000), 2) as avg_latency_ms,
  ROUND(APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(95)], 2) as p95_latency_ms,
  STRING_AGG(DISTINCT JSON_EXTRACT_SCALAR(attributes, '$.db.statement') LIMIT 3) as sample_statements,
  ANY_VALUE(JSON_EXTRACT_SCALAR(attributes, '$.db.statement')) as `db.statement`
FROM `{dataset_id}.{table_name}`
WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)
  AND kind = 3 -- CLIENT
  {where_extra}
GROUP BY 1, 2, 3
ORDER BY call_count DESC
"""
    return json.dumps(
        {
            "analysis_type": "database_operations",
            "sql_query": query.strip(),
            "description": "Analyze database operations",
        }
    )
