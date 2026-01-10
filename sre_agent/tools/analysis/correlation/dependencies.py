"""Service dependency analysis tools for distributed systems debugging.

Traces reveal the true runtime topology of a distributed system. This module
analyzes trace data to build accurate service dependency graphs, identify
failure propagation paths, and detect architectural issues.

Key capabilities:
- Build service dependency graph from traces
- Analyze upstream/downstream impact of failures
- Detect circular dependencies and other anti-patterns
- Find hidden dependencies not in documentation

References:
- https://cloud.google.com/trace/docs/trace-log-integration
- https://opentelemetry.io/docs/concepts/signals/traces/
"""

import json
import logging
from typing import Any

from ...common import adk_tool
from ...common.telemetry import get_tracer, get_meter

logger = logging.getLogger(__name__)

tracer = get_tracer(__name__)
meter = get_meter(__name__)

dependency_operations = meter.create_counter(
    name="sre_agent.dependency.operations",
    description="Count of dependency analysis operations",
    unit="1",
)


@adk_tool
def build_service_dependency_graph(
    dataset_id: str,
    table_name: str = "_AllSpans",
    time_window_hours: int = 24,
    min_call_count: int = 10,
    include_external: bool = True,
) -> str:
    """
    Builds a service dependency graph from trace data.

    Analyzes CLIENT spans (outgoing calls) to determine which services
    depend on which other services. This is the actual runtime topology,
    not the designed architecture - they often differ!

    Args:
        dataset_id: BigQuery dataset containing trace data
        table_name: Table name containing OTel traces
        time_window_hours: Time window for analysis
        min_call_count: Minimum number of calls to include a dependency
        include_external: Include external services (databases, APIs, etc.)

    Returns:
        JSON with SQL query for dependency graph and visualization data
    """
    with tracer.start_as_current_span("build_service_dependency_graph") as span:
        dependency_operations.add(1, {"type": "build_graph"})

        sql = f"""
-- Build service dependency graph from trace CLIENT spans
-- CLIENT spans represent outgoing calls from one service to another

WITH service_calls AS (
  SELECT
    -- Caller (source) service
    JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') as source_service,
    -- Callee (target) service - from span attributes or name
    COALESCE(
      JSON_EXTRACT_SCALAR(attributes, '$.peer.service'),
      JSON_EXTRACT_SCALAR(attributes, '$.net.peer.name'),
      JSON_EXTRACT_SCALAR(attributes, '$.db.system'),
      JSON_EXTRACT_SCALAR(attributes, '$.rpc.service'),
      JSON_EXTRACT_SCALAR(attributes, '$.http.host'),
      REGEXP_EXTRACT(name, r'^([^/]+)')  -- First part of span name
    ) as target_service,
    trace_id,
    span_id,
    name as operation_name,
    duration_nano / 1000000 as duration_ms,
    status.code as status_code,
    kind,
    -- Extract call type
    CASE
      WHEN JSON_EXTRACT_SCALAR(attributes, '$.db.system') IS NOT NULL THEN 'DATABASE'
      WHEN JSON_EXTRACT_SCALAR(attributes, '$.rpc.system') IS NOT NULL THEN 'RPC'
      WHEN JSON_EXTRACT_SCALAR(attributes, '$.http.method') IS NOT NULL THEN 'HTTP'
      WHEN JSON_EXTRACT_SCALAR(attributes, '$.messaging.system') IS NOT NULL THEN 'MESSAGING'
      ELSE 'INTERNAL'
    END as call_type
  FROM `{dataset_id}.{table_name}`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)
    AND kind = 3  -- CLIENT spans only
    AND JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') IS NOT NULL
),
dependency_edges AS (
  SELECT
    source_service,
    target_service,
    call_type,
    COUNT(*) as call_count,
    COUNT(DISTINCT trace_id) as trace_count,
    ROUND(AVG(duration_ms), 2) as avg_latency_ms,
    ROUND(APPROX_QUANTILES(duration_ms, 100)[OFFSET(95)], 2) as p95_latency_ms,
    ROUND(COUNTIF(status_code = 2) / COUNT(*) * 100, 2) as error_rate_pct,
    -- Calculate dependency strength (normalized)
    ROUND(COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY source_service) * 100, 2) as dependency_weight_pct,
    -- Collect sample operations
    STRING_AGG(DISTINCT operation_name LIMIT 5) as sample_operations
  FROM service_calls
  WHERE target_service IS NOT NULL
    AND target_service != source_service  -- Exclude self-calls
  GROUP BY source_service, target_service, call_type
  HAVING call_count >= {min_call_count}
)
SELECT
  source_service,
  target_service,
  call_type,
  call_count,
  trace_count,
  avg_latency_ms,
  p95_latency_ms,
  error_rate_pct,
  dependency_weight_pct,
  sample_operations,
  -- Health indicator
  CASE
    WHEN error_rate_pct > 5 THEN 'UNHEALTHY'
    WHEN error_rate_pct > 1 THEN 'DEGRADED'
    ELSE 'HEALTHY'
  END as dependency_health,
  -- Criticality based on call volume and weight
  CASE
    WHEN dependency_weight_pct > 50 THEN 'CRITICAL'
    WHEN dependency_weight_pct > 20 THEN 'HIGH'
    WHEN dependency_weight_pct > 5 THEN 'MEDIUM'
    ELSE 'LOW'
  END as criticality
FROM dependency_edges
ORDER BY source_service, dependency_weight_pct DESC
"""

        # SQL to find isolated services (potential orphans or entry points)
        topology_sql = f"""
-- Find service topology characteristics

WITH all_services AS (
  SELECT DISTINCT JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') as service_name
  FROM `{dataset_id}.{table_name}`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)
    AND JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') IS NOT NULL
),
callers AS (
  SELECT DISTINCT JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') as service_name
  FROM `{dataset_id}.{table_name}`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)
    AND kind = 3  -- CLIENT spans
),
callees AS (
  SELECT DISTINCT
    COALESCE(
      JSON_EXTRACT_SCALAR(attributes, '$.peer.service'),
      JSON_EXTRACT_SCALAR(attributes, '$.net.peer.name')
    ) as service_name
  FROM `{dataset_id}.{table_name}`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)
    AND kind = 3
)
SELECT
  a.service_name,
  a.service_name IN (SELECT service_name FROM callers) as makes_outgoing_calls,
  a.service_name IN (SELECT service_name FROM callees) as receives_incoming_calls,
  CASE
    WHEN a.service_name NOT IN (SELECT service_name FROM callers)
         AND a.service_name IN (SELECT service_name FROM callees) THEN 'LEAF'
    WHEN a.service_name IN (SELECT service_name FROM callers)
         AND a.service_name NOT IN (SELECT service_name FROM callees) THEN 'ENTRY_POINT'
    WHEN a.service_name IN (SELECT service_name FROM callers)
         AND a.service_name IN (SELECT service_name FROM callees) THEN 'INTERMEDIATE'
    ELSE 'ISOLATED'
  END as topology_role
FROM all_services a
ORDER BY topology_role, service_name
"""

        result = {
            "analysis_type": "service_dependency_graph",
            "dependency_graph_sql": sql.strip(),
            "topology_sql": topology_sql.strip(),
            "output_format": {
                "nodes": "Each unique service_name (source or target)",
                "edges": "source_service -> target_service with call_type and metrics",
            },
            "metrics_explained": {
                "call_count": "Total number of calls in time window",
                "trace_count": "Number of distinct traces using this edge",
                "dependency_weight_pct": "% of source's outgoing calls to this target",
                "criticality": "Impact level if this dependency fails",
                "dependency_health": "Current health based on error rate",
            },
            "topology_roles": {
                "ENTRY_POINT": "Services that make calls but don't receive any (frontends, APIs)",
                "INTERMEDIATE": "Services that both receive and make calls (middleware)",
                "LEAF": "Services that receive calls but don't make any (databases, storage)",
                "ISOLATED": "Services with no detected dependencies (may be instrumentation gap)",
            },
            "visualization_hint": (
                "Use the edges from dependency_graph_sql to build a directed graph. "
                "Color nodes by topology_role and edges by dependency_health."
            ),
            "next_steps": [
                "Execute dependency_graph_sql using BigQuery MCP execute_sql",
                "Execute topology_sql to understand service roles",
                "Identify CRITICAL dependencies with UNHEALTHY status",
                "Look for unexpected dependencies not in architecture docs",
            ],
        }

        logger.info("Generated service dependency graph SQL")
        return json.dumps(result)


@adk_tool
def analyze_upstream_downstream_impact(
    dataset_id: str,
    service_name: str,
    table_name: str = "_AllSpans",
    time_window_hours: int = 24,
    depth: int = 3,
) -> str:
    """
    Analyzes the upstream and downstream impact of a service.

    Upstream: Services that call this service (who would be affected if it fails)
    Downstream: Services this service calls (whose failures would affect it)

    This is critical for understanding blast radius during incidents.

    Args:
        dataset_id: BigQuery dataset containing trace data
        service_name: The service to analyze
        table_name: Table name containing OTel traces
        time_window_hours: Time window for analysis
        depth: How many hops to traverse (default: 3)

    Returns:
        JSON with SQL query for impact analysis
    """
    with tracer.start_as_current_span("analyze_upstream_downstream_impact") as span:
        span.set_attribute("service_name", service_name)
        dependency_operations.add(1, {"type": "impact_analysis"})

        # Recursive CTE to find multi-hop dependencies
        sql = f"""
-- Analyze upstream (callers) and downstream (callees) of a service
-- This shows the blast radius if the service fails

WITH RECURSIVE
-- Direct dependencies from trace data
direct_deps AS (
  SELECT
    JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') as source_service,
    COALESCE(
      JSON_EXTRACT_SCALAR(attributes, '$.peer.service'),
      JSON_EXTRACT_SCALAR(attributes, '$.net.peer.name'),
      JSON_EXTRACT_SCALAR(attributes, '$.db.system'),
      JSON_EXTRACT_SCALAR(attributes, '$.rpc.service')
    ) as target_service,
    COUNT(*) as call_count,
    ROUND(COUNTIF(status.code = 2) / COUNT(*) * 100, 2) as error_rate_pct,
    ROUND(APPROX_QUANTILES(duration_nano / 1000000, 100)[OFFSET(95)], 2) as p95_latency_ms
  FROM `{dataset_id}.{table_name}`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)
    AND kind = 3
  GROUP BY 1, 2
  HAVING target_service IS NOT NULL AND source_service IS NOT NULL
),

-- Services that call our target (upstream / callers)
-- These would be impacted if target fails
upstream AS (
  SELECT
    source_service as service,
    1 as depth,
    'DIRECT_CALLER' as relationship,
    call_count,
    error_rate_pct,
    p95_latency_ms,
    ARRAY[source_service] as path
  FROM direct_deps
  WHERE target_service = '{service_name}'

  UNION ALL

  SELECT
    d.source_service as service,
    u.depth + 1 as depth,
    'INDIRECT_CALLER' as relationship,
    d.call_count,
    d.error_rate_pct,
    d.p95_latency_ms,
    ARRAY_CONCAT(u.path, [d.source_service]) as path
  FROM direct_deps d
  JOIN upstream u ON d.target_service = u.service
  WHERE u.depth < {depth}
    AND d.source_service NOT IN UNNEST(u.path)  -- Avoid cycles
),

-- Services that our target calls (downstream / dependencies)
-- If these fail, our target would be impacted
downstream AS (
  SELECT
    target_service as service,
    1 as depth,
    'DIRECT_DEPENDENCY' as relationship,
    call_count,
    error_rate_pct,
    p95_latency_ms,
    ARRAY[target_service] as path
  FROM direct_deps
  WHERE source_service = '{service_name}'

  UNION ALL

  SELECT
    d.target_service as service,
    dn.depth + 1 as depth,
    'INDIRECT_DEPENDENCY' as relationship,
    d.call_count,
    d.error_rate_pct,
    d.p95_latency_ms,
    ARRAY_CONCAT(dn.path, [d.target_service]) as path
  FROM direct_deps d
  JOIN downstream dn ON d.source_service = dn.service
  WHERE dn.depth < {depth}
    AND d.target_service NOT IN UNNEST(dn.path)  -- Avoid cycles
)

-- Combine upstream and downstream with the target service
SELECT
  '{service_name}' as target_service,
  'UPSTREAM' as direction,
  service as related_service,
  depth,
  relationship,
  call_count,
  error_rate_pct,
  p95_latency_ms,
  ARRAY_TO_STRING(path, ' -> ') as dependency_path
FROM upstream

UNION ALL

SELECT
  '{service_name}' as target_service,
  'DOWNSTREAM' as direction,
  service as related_service,
  depth,
  relationship,
  call_count,
  error_rate_pct,
  p95_latency_ms,
  ARRAY_TO_STRING(path, ' -> ') as dependency_path
FROM downstream

ORDER BY direction, depth, call_count DESC
"""

        result = {
            "analysis_type": "upstream_downstream_impact",
            "target_service": service_name,
            "analysis_depth": depth,
            "sql_query": sql.strip(),
            "directions_explained": {
                "UPSTREAM": (
                    f"Services that call {service_name}. "
                    f"These would experience failures if {service_name} is down."
                ),
                "DOWNSTREAM": (
                    f"Services that {service_name} depends on. "
                    f"If these fail, {service_name} would be impacted."
                ),
            },
            "relationships": {
                "DIRECT_CALLER": "Calls target service directly (1 hop)",
                "INDIRECT_CALLER": "Reaches target through other services (2+ hops)",
                "DIRECT_DEPENDENCY": "Target service calls this directly (1 hop)",
                "INDIRECT_DEPENDENCY": "Reachable from target through other services (2+ hops)",
            },
            "incident_response_usage": {
                "if_target_fails": "Look at UPSTREAM services - they will experience errors",
                "if_target_slow": "UPSTREAM services will see increased latency",
                "diagnose_target_issues": "Check DOWNSTREAM services for root cause",
            },
            "next_steps": [
                "Execute SQL using BigQuery MCP execute_sql",
                "For UPSTREAM with high call_count - expect significant user impact",
                "For DOWNSTREAM with high error_rate - likely root cause candidates",
                "Check dependency_path for unexpected routing",
            ],
        }

        logger.info(f"Generated impact analysis SQL for {service_name}")
        return json.dumps(result)


@adk_tool
def detect_circular_dependencies(
    dataset_id: str,
    table_name: str = "_AllSpans",
    time_window_hours: int = 24,
    max_cycle_length: int = 5,
) -> str:
    """
    Detects circular dependencies in the service graph.

    Circular dependencies (A -> B -> C -> A) can cause:
    - Deadlocks under load
    - Cascading failures that loop
    - Difficulty in deployment ordering
    - Hidden coupling

    Args:
        dataset_id: BigQuery dataset containing trace data
        table_name: Table name containing OTel traces
        time_window_hours: Time window for analysis
        max_cycle_length: Maximum cycle length to search for

    Returns:
        JSON with SQL query to detect cycles
    """
    with tracer.start_as_current_span("detect_circular_dependencies") as span:
        dependency_operations.add(1, {"type": "detect_cycles"})

        # Note: BigQuery doesn't support recursive CTEs well for cycle detection
        # So we use a self-join approach for small cycle lengths
        sql = f"""
-- Detect circular dependencies in service graph
-- Looking for A -> B -> A (length 2) and A -> B -> C -> A (length 3) patterns

WITH service_edges AS (
  SELECT DISTINCT
    JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') as source,
    COALESCE(
      JSON_EXTRACT_SCALAR(attributes, '$.peer.service'),
      JSON_EXTRACT_SCALAR(attributes, '$.net.peer.name'),
      JSON_EXTRACT_SCALAR(attributes, '$.rpc.service')
    ) as target
  FROM `{dataset_id}.{table_name}`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)
    AND kind = 3
    AND JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') IS NOT NULL
),

-- Length 2 cycles: A -> B -> A
cycles_2 AS (
  SELECT
    e1.source as service_1,
    e1.target as service_2,
    e1.source as completes_cycle,
    2 as cycle_length,
    CONCAT(e1.source, ' -> ', e1.target, ' -> ', e1.source) as cycle_path
  FROM service_edges e1
  JOIN service_edges e2 ON e1.target = e2.source AND e2.target = e1.source
  WHERE e1.source < e1.target  -- Avoid duplicate cycles
),

-- Length 3 cycles: A -> B -> C -> A
cycles_3 AS (
  SELECT
    e1.source as service_1,
    e1.target as service_2,
    e2.target as service_3,
    3 as cycle_length,
    CONCAT(e1.source, ' -> ', e1.target, ' -> ', e2.target, ' -> ', e1.source) as cycle_path
  FROM service_edges e1
  JOIN service_edges e2 ON e1.target = e2.source
  JOIN service_edges e3 ON e2.target = e3.source AND e3.target = e1.source
  WHERE e1.source != e2.target  -- Not a 2-cycle
    AND e1.source < e1.target  -- Avoid duplicates
    AND e1.target < e2.target
),

-- Length 4 cycles: A -> B -> C -> D -> A
cycles_4 AS (
  SELECT
    e1.source as service_1,
    e1.target as service_2,
    e2.target as service_3,
    4 as cycle_length,
    CONCAT(e1.source, ' -> ', e1.target, ' -> ', e2.target, ' -> ', e3.target, ' -> ', e1.source) as cycle_path
  FROM service_edges e1
  JOIN service_edges e2 ON e1.target = e2.source
  JOIN service_edges e3 ON e2.target = e3.source
  JOIN service_edges e4 ON e3.target = e4.source AND e4.target = e1.source
  WHERE e1.source != e2.target AND e1.source != e3.target
    AND e1.target != e3.target
)

SELECT * FROM cycles_2
UNION ALL
SELECT service_1, service_2, service_3, cycle_length, cycle_path FROM cycles_3
UNION ALL
SELECT service_1, service_2, service_3, cycle_length, cycle_path FROM cycles_4
ORDER BY cycle_length, cycle_path
"""

        result = {
            "analysis_type": "circular_dependency_detection",
            "sql_query": sql.strip(),
            "max_cycle_length_searched": min(max_cycle_length, 4),
            "why_cycles_are_problematic": {
                "deadlock_risk": "Under load, circular calls can create deadlocks",
                "cascading_failures": "Errors can loop indefinitely through the cycle",
                "deployment_ordering": "No safe order to deploy/restart services",
                "testing_difficulty": "Hard to test services in isolation",
                "tight_coupling": "Services become tightly coupled, reducing flexibility",
            },
            "common_cycle_patterns": {
                "callback_pattern": "A calls B, B calls back to A (often intentional)",
                "cache_invalidation": "Service A invalidates cache in B, B checks state in A",
                "event_driven": "Async events flowing in circles",
                "configuration": "Distributed config where services update each other",
            },
            "resolution_strategies": {
                "break_with_async": "Convert synchronous call to async message",
                "consolidate_services": "Merge tightly coupled services",
                "introduce_mediator": "Add a coordinator service",
                "redesign_ownership": "Clarify data/responsibility ownership",
            },
            "next_steps": [
                "Execute SQL using BigQuery MCP execute_sql",
                "Analyze each cycle to determine if intentional",
                "For unintentional cycles, plan architectural changes",
                "Use analyze_upstream_downstream_impact to understand full impact",
            ],
        }

        logger.info("Generated circular dependency detection SQL")
        return json.dumps(result)


@adk_tool
def find_hidden_dependencies(
    dataset_id: str,
    table_name: str = "_AllSpans",
    time_window_hours: int = 24,
    min_call_count: int = 5,
) -> str:
    """
    Finds dependencies that may not be in official architecture documentation.

    Hidden dependencies are discovered by analyzing trace data for:
    - Calls to external services
    - Database connections
    - Third-party API calls
    - Internal services not in diagrams

    Args:
        dataset_id: BigQuery dataset containing trace data
        table_name: Table name containing OTel traces
        time_window_hours: Time window for analysis
        min_call_count: Minimum calls to consider a real dependency

    Returns:
        JSON with SQL query to find hidden dependencies
    """
    with tracer.start_as_current_span("find_hidden_dependencies") as span:
        dependency_operations.add(1, {"type": "hidden_deps"})

        sql = f"""
-- Find potentially hidden or undocumented dependencies
-- by analyzing CLIENT span attributes for external connections

WITH external_calls AS (
  SELECT
    JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') as source_service,
    -- Identify the target from various attribute patterns
    COALESCE(
      JSON_EXTRACT_SCALAR(attributes, '$.peer.service'),
      JSON_EXTRACT_SCALAR(attributes, '$.net.peer.name'),
      JSON_EXTRACT_SCALAR(attributes, '$.db.system'),
      JSON_EXTRACT_SCALAR(attributes, '$.rpc.service'),
      JSON_EXTRACT_SCALAR(attributes, '$.http.host'),
      JSON_EXTRACT_SCALAR(attributes, '$.messaging.destination'),
      JSON_EXTRACT_SCALAR(attributes, '$.faas.invoked_provider'),
      -- Parse from span name as fallback
      REGEXP_EXTRACT(name, r'^([A-Za-z0-9_-]+)')
    ) as target_identifier,
    -- Categorize the dependency type
    CASE
      WHEN JSON_EXTRACT_SCALAR(attributes, '$.db.system') IS NOT NULL THEN 'DATABASE'
      WHEN JSON_EXTRACT_SCALAR(attributes, '$.messaging.system') IS NOT NULL THEN 'MESSAGE_QUEUE'
      WHEN JSON_EXTRACT_SCALAR(attributes, '$.rpc.system') = 'grpc' THEN 'GRPC_SERVICE'
      WHEN JSON_EXTRACT_SCALAR(attributes, '$.http.host') LIKE '%.googleapis.com' THEN 'GCP_API'
      WHEN JSON_EXTRACT_SCALAR(attributes, '$.http.host') LIKE '%.aws.%' THEN 'AWS_API'
      WHEN JSON_EXTRACT_SCALAR(attributes, '$.http.host') IS NOT NULL THEN 'HTTP_EXTERNAL'
      WHEN JSON_EXTRACT_SCALAR(attributes, '$.faas.invoked_provider') IS NOT NULL THEN 'CLOUD_FUNCTION'
      ELSE 'INTERNAL_SERVICE'
    END as dependency_type,
    -- Get specific details
    JSON_EXTRACT_SCALAR(attributes, '$.db.system') as db_system,
    JSON_EXTRACT_SCALAR(attributes, '$.db.name') as db_name,
    JSON_EXTRACT_SCALAR(attributes, '$.http.host') as http_host,
    JSON_EXTRACT_SCALAR(attributes, '$.http.url') as http_url,
    JSON_EXTRACT_SCALAR(attributes, '$.messaging.destination') as queue_name,
    name as operation_name,
    duration_nano / 1000000 as duration_ms,
    status.code as status_code
  FROM `{dataset_id}.{table_name}`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)
    AND kind = 3  -- CLIENT spans
    AND JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') IS NOT NULL
)
SELECT
  source_service,
  target_identifier,
  dependency_type,
  -- Additional details based on type
  CASE
    WHEN dependency_type = 'DATABASE' THEN CONCAT(db_system, '/', COALESCE(db_name, 'unknown'))
    WHEN dependency_type LIKE '%EXTERNAL' THEN http_host
    WHEN dependency_type = 'MESSAGE_QUEUE' THEN queue_name
    ELSE target_identifier
  END as target_details,
  COUNT(*) as call_count,
  COUNT(DISTINCT operation_name) as unique_operations,
  ROUND(AVG(duration_ms), 2) as avg_latency_ms,
  ROUND(APPROX_QUANTILES(duration_ms, 100)[OFFSET(95)], 2) as p95_latency_ms,
  ROUND(COUNTIF(status_code = 2) / COUNT(*) * 100, 2) as error_rate_pct,
  STRING_AGG(DISTINCT operation_name LIMIT 5) as sample_operations,
  -- Flag for review priority
  CASE
    WHEN dependency_type LIKE '%EXTERNAL%' THEN 'HIGH'  -- External deps need documentation
    WHEN dependency_type = 'DATABASE' AND db_name IS NULL THEN 'HIGH'  -- Unknown DB
    WHEN error_rate_pct > 5 THEN 'HIGH'  -- Unreliable dependency
    WHEN call_count > 1000 THEN 'MEDIUM'  -- High volume
    ELSE 'LOW'
  END as documentation_priority
FROM external_calls
WHERE target_identifier IS NOT NULL
GROUP BY
  source_service,
  target_identifier,
  dependency_type,
  db_system,
  db_name,
  http_host,
  queue_name
HAVING call_count >= {min_call_count}
ORDER BY source_service, documentation_priority DESC, call_count DESC
"""

        result = {
            "analysis_type": "hidden_dependencies",
            "sql_query": sql.strip(),
            "dependency_types": {
                "DATABASE": "Calls to database systems (PostgreSQL, MySQL, Redis, etc.)",
                "MESSAGE_QUEUE": "Calls to message brokers (Kafka, Pub/Sub, RabbitMQ)",
                "GRPC_SERVICE": "gRPC calls to other services",
                "GCP_API": "Calls to Google Cloud APIs",
                "AWS_API": "Calls to AWS APIs",
                "HTTP_EXTERNAL": "HTTP calls to external services",
                "CLOUD_FUNCTION": "Invocations of serverless functions",
                "INTERNAL_SERVICE": "Calls to internal services",
            },
            "documentation_priority_meaning": {
                "HIGH": "Should definitely be in architecture docs",
                "MEDIUM": "Worth documenting for operational awareness",
                "LOW": "Low risk, document if maintaining full inventory",
            },
            "common_hidden_dependency_issues": {
                "undocumented_database": "Service using a database not in architecture",
                "shadow_api": "Calls to external APIs without proper contracts",
                "implicit_coupling": "Services coupled through shared database",
                "legacy_integration": "Old integrations forgotten but still active",
            },
            "next_steps": [
                "Execute SQL using BigQuery MCP execute_sql",
                "Compare results with official architecture documentation",
                "Prioritize documenting HIGH priority items",
                "Check error_rate for reliability concerns",
                "Validate external API contracts exist",
            ],
        }

        logger.info("Generated hidden dependencies analysis SQL")
        return json.dumps(result)
