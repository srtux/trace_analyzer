"""BigQuery-powered log pattern analysis.

This module provides tools to analyze log patterns using BigQuery's regex functions,
enabling efficient clustering of millions of logs without client-side processing.
"""

import json
import logging

from ...common import adk_tool

logger = logging.getLogger(__name__)


@adk_tool
def analyze_bigquery_log_patterns(
    dataset_id: str,
    table_name: str,
    time_window_hours: int = 24,
    service_name: str | None = None,
    severity: str | None = None,
    limit: int = 50,
) -> str:
    """Analyzes log patterns in BigQuery using SQL-based clustering.

    This tool is equivalent to 'Drain' pattern analysis but runs entirely in BigQuery,
    capable of processing millions of logs in seconds. It masks variable content
    (timestamps, UUIDs, Numbers, IPs) to group similar logs.

    Args:
        dataset_id: BigQuery dataset ID
        table_name: Table name containing logs (e.g., '_AllLogs')
        time_window_hours: Analysis window size
        service_name: Optional filter for specific service
        severity: Optional severity filter (e.g., 'ERROR')
        limit: Max patterns to return

    Returns:
        JSON with SQL query to extract top patterns.
    """
    where_conditions = [
        f"timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)",
    ]

    if service_name:
        where_conditions.append(
            f"JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') = '{service_name}'"
        )

    if severity:
        where_conditions.append(f"severity_text = '{severity}'")

    where_clause = " AND ".join(where_conditions)

    # Complex regex replacement to mask variables
    # Order matters: specific patterns first

    # Mask specific known patterns
    replacements = [
        # Mask UUIDs (8-4-4-4-12 hex)
        (
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            "<UUID>",
        ),
        # Mask IPv4
        (r"\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}", "<IP>"),
        # Mask Timestamp ISO8601-ish (YYYY-MM-DD...)
        (r"\\d{4}-\\d{2}-\\d{2}[T ]\\d{2}:\\d{2}:\\d{2}", "<TIMESTAMP>"),
        # Mask Hex pointers or large hex numbers (0x...)
        (r"0x[0-9a-fA-F]+", "<HEX>"),
        # Mask generic numbers (sequences of digits)
        (r"\\d+", "<NUM>"),
        # Mask Emails
        (r"[\\w\\.-]+@[\\w\\.-]+\\.\\w+", "<EMAIL>"),
    ]

    # Nest the REGEXP_REPLACE calls
    expression = "body.string_value"
    for pattern, replacement in replacements:
        expression = f"REGEXP_REPLACE({expression}, r'{pattern}', '{replacement}')"

    query = f"""
SELECT
  {expression} as pattern_signature,
  COUNT(*) as occurrence_count,
  ANY_VALUE(body.string_value) as sample_log,
  STRING_AGG(DISTINCT severity_text, ',') as severities,
  MIN(timestamp) as first_seen,
  MAX(timestamp) as last_seen
FROM `{dataset_id}.{table_name}`
WHERE {where_clause}
GROUP BY 1
ORDER BY occurrence_count DESC
LIMIT {limit}
"""

    logger.info(f"Generated BigQuery Log Pattern SQL:\n{query.strip()}")

    return json.dumps(
        {
            "analysis_type": "bigquery_log_patterns",
            "sql_query": query.strip(),
            "description": f"Top {limit} log patterns for {service_name or 'all services'} in last {time_window_hours}h",
            "next_steps": [
                "Execute this query using BigQuery MCP execute_sql tool",
                "Start with 'ERROR' severity patterns",
                "Compare pattern counts to baseline using compare_time_periods logic manually",
            ],
        }
    )
