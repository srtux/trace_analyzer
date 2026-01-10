"""Critical path analysis tools for distributed trace debugging.

The critical path is the longest-duration path through the trace - the sequence
of operations that directly contribute to the total request latency. Optimizing
operations on the critical path yields the greatest latency improvements.

Key concepts:
- Critical path: The chain of operations that determines total latency
- Slack: Operations NOT on critical path (can be slower without affecting latency)
- Bottleneck: The single span contributing most to critical path duration

References:
- https://queue.acm.org/detail.cfm?id=3526967 (Distributed Latency Profiling)
- https://cloud.google.com/blog/products/devops-sre/introducing-the-new-google-cloud-trace-explorer
"""

import json
import logging
from typing import Any

from ...common import adk_tool
from ...common.telemetry import get_tracer, get_meter
from ...clients.trace import fetch_trace_data

logger = logging.getLogger(__name__)

tracer = get_tracer(__name__)
meter = get_meter(__name__)

critical_path_operations = meter.create_counter(
    name="sre_agent.critical_path.operations",
    description="Count of critical path analysis operations",
    unit="1",
)


@adk_tool
def analyze_critical_path(
    trace_id: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """
    Analyzes the critical path of a distributed trace.

    The critical path is the chain of spans that determines the total latency
    of the request. Operations on the critical path MUST complete for the
    request to finish - optimizing these yields the greatest improvements.

    Args:
        trace_id: The trace ID to analyze
        project_id: The Google Cloud Project ID

    Returns:
        Dictionary with:
        - critical_path: Ordered list of spans on the critical path
        - critical_path_duration_ms: Total duration of critical path
        - bottleneck_span: The single span contributing most to latency
        - parallel_opportunities: Spans that could be parallelized
        - optimization_recommendations: Specific suggestions
    """
    with tracer.start_as_current_span("analyze_critical_path") as span:
        span.set_attribute("trace_id", trace_id)
        critical_path_operations.add(1, {"type": "analyze"})

        # Fetch trace data
        trace = fetch_trace_data(trace_id, project_id)
        if "error" in trace:
            return {"error": trace["error"]}

        spans = trace.get("spans", [])
        if not spans:
            return {"error": "No spans found in trace"}

        # Build span lookup and timing data
        span_map = {}
        children_map: dict[str, list[str]] = {}

        for s in spans:
            span_id = s.get("span_id")
            parent_id = s.get("parent_span_id")

            if span_id:
                # Parse timestamps
                start_time = s.get("start_time", "")
                end_time = s.get("end_time", "")

                # Calculate duration
                duration_ms = 0
                if start_time and end_time:
                    from datetime import datetime
                    try:
                        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                        duration_ms = (end_dt - start_dt).total_seconds() * 1000
                    except (ValueError, TypeError):
                        pass

                span_map[span_id] = {
                    "span_id": span_id,
                    "parent_id": parent_id,
                    "name": s.get("name", "unknown"),
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration_ms": duration_ms,
                    "service": _extract_service_name(s),
                    "status_code": s.get("labels", {}).get("status.code", 0),
                    "is_error": _is_error_span(s),
                    "kind": s.get("kind", "INTERNAL"),
                    "labels": s.get("labels", {}),
                }

                if parent_id:
                    if parent_id not in children_map:
                        children_map[parent_id] = []
                    children_map[parent_id].append(span_id)

        # Find root spans
        root_spans = [s for s in span_map.values() if not s.get("parent_id")]

        if not root_spans:
            return {"error": "No root span found in trace"}

        # For each root, calculate critical path
        all_critical_paths = []
        for root in root_spans:
            path = _calculate_critical_path(root["span_id"], span_map, children_map)
            all_critical_paths.append(path)

        # Take the longest critical path as THE critical path
        critical_path = max(all_critical_paths, key=lambda p: p["total_duration_ms"])

        # Find the bottleneck (span with highest self-time on critical path)
        bottleneck = None
        max_self_time = 0
        for span_info in critical_path["spans"]:
            if span_info["self_time_ms"] > max_self_time:
                max_self_time = span_info["self_time_ms"]
                bottleneck = span_info

        # Find parallelization opportunities
        parallel_opportunities = _find_parallel_opportunities(span_map, children_map)

        # Generate optimization recommendations
        recommendations = _generate_optimization_recommendations(
            critical_path, bottleneck, parallel_opportunities, span_map
        )

        result = {
            "trace_id": trace_id,
            "total_spans": len(spans),
            "critical_path": {
                "spans": critical_path["spans"],
                "total_duration_ms": critical_path["total_duration_ms"],
                "span_count": len(critical_path["spans"]),
                "services_on_path": list(set(
                    s["service"] for s in critical_path["spans"] if s["service"]
                )),
            },
            "bottleneck_span": bottleneck,
            "parallel_opportunities": parallel_opportunities[:5],  # Top 5
            "optimization_recommendations": recommendations,
            "analysis_summary": {
                "critical_path_ratio": round(
                    critical_path["total_duration_ms"] /
                    max(s["duration_ms"] for s in span_map.values()) * 100, 1
                ) if span_map else 0,
                "bottleneck_contribution": round(
                    max_self_time / critical_path["total_duration_ms"] * 100, 1
                ) if critical_path["total_duration_ms"] > 0 else 0,
                "potential_parallelization_savings_ms": sum(
                    p.get("potential_savings_ms", 0) for p in parallel_opportunities[:5]
                ),
            },
        }

        span.set_attribute("sre_agent.critical_path.span_count", len(critical_path["spans"]))
        span.set_attribute("sre_agent.critical_path.duration_ms", critical_path["total_duration_ms"])

        return result


def _extract_service_name(span: dict) -> str | None:
    """Extract service name from span labels/attributes."""
    labels = span.get("labels", {})
    # Try common attribute names
    for key in ["service.name", "/service.name", "g.co/service.name"]:
        if key in labels:
            return labels[key]
    return None


def _is_error_span(span: dict) -> bool:
    """Check if span represents an error."""
    labels = span.get("labels", {})
    # Check status code
    status = labels.get("status.code", labels.get("/http/status_code", 0))
    try:
        code = int(status)
        if code >= 400:
            return True
    except (ValueError, TypeError):
        pass
    # Check error labels
    for key in labels:
        if "error" in key.lower():
            val = str(labels[key]).lower()
            if val not in ("false", "0", "none", "ok", ""):
                return True
    return False


def _calculate_critical_path(
    span_id: str,
    span_map: dict[str, dict],
    children_map: dict[str, list[str]],
) -> dict[str, Any]:
    """
    Recursively calculate the critical path from a span.

    The critical path is the path through child spans that has the longest
    total duration. We track both wall-clock duration and self-time.
    """
    span = span_map.get(span_id)
    if not span:
        return {"spans": [], "total_duration_ms": 0}

    children_ids = children_map.get(span_id, [])

    if not children_ids:
        # Leaf span - it IS its own critical path
        return {
            "spans": [{
                "span_id": span_id,
                "name": span["name"],
                "service": span["service"],
                "duration_ms": span["duration_ms"],
                "self_time_ms": span["duration_ms"],  # No children = all self time
                "is_error": span["is_error"],
                "depth": 0,
            }],
            "total_duration_ms": span["duration_ms"],
        }

    # Get critical paths for all children
    child_paths = []
    for child_id in children_ids:
        child_path = _calculate_critical_path(child_id, span_map, children_map)
        child_paths.append(child_path)

    # The child with the longest path is on our critical path
    longest_child_path = max(child_paths, key=lambda p: p["total_duration_ms"])

    # Calculate self-time (duration minus time spent in children)
    total_child_duration = sum(
        span_map[cid]["duration_ms"] for cid in children_ids
        if cid in span_map
    )
    self_time = max(0, span["duration_ms"] - total_child_duration)

    # Build our critical path entry
    current_span_entry = {
        "span_id": span_id,
        "name": span["name"],
        "service": span["service"],
        "duration_ms": span["duration_ms"],
        "self_time_ms": self_time,
        "is_error": span["is_error"],
        "child_count": len(children_ids),
        "depth": 0,
    }

    # Increment depth for child spans
    for child_entry in longest_child_path["spans"]:
        child_entry["depth"] = child_entry.get("depth", 0) + 1

    return {
        "spans": [current_span_entry] + longest_child_path["spans"],
        "total_duration_ms": span["duration_ms"],
    }


def _find_parallel_opportunities(
    span_map: dict[str, dict],
    children_map: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """
    Find spans that could potentially be parallelized.

    Looks for sequential sibling calls to the same service or similar operations
    that might benefit from batching or concurrent execution.
    """
    opportunities = []

    for parent_id, children_ids in children_map.items():
        if len(children_ids) < 2:
            continue

        # Group children by service
        service_groups: dict[str, list[dict]] = {}
        for child_id in children_ids:
            child = span_map.get(child_id)
            if child:
                service = child.get("service") or "unknown"
                if service not in service_groups:
                    service_groups[service] = []
                service_groups[service].append(child)

        # Look for multiple sequential calls to same service
        for service, group in service_groups.items():
            if len(group) >= 2:
                # Check if they appear to be sequential (non-overlapping times)
                # Sort by start time
                sorted_spans = sorted(group, key=lambda s: s.get("start_time", ""))

                total_duration = sum(s["duration_ms"] for s in sorted_spans)
                max_duration = max(s["duration_ms"] for s in sorted_spans)
                potential_savings = total_duration - max_duration

                if potential_savings > 10:  # At least 10ms savings
                    opportunities.append({
                        "type": "sequential_same_service",
                        "service": service,
                        "span_count": len(group),
                        "span_names": [s["name"] for s in sorted_spans[:3]],
                        "total_sequential_duration_ms": round(total_duration, 2),
                        "potential_parallel_duration_ms": round(max_duration, 2),
                        "potential_savings_ms": round(potential_savings, 2),
                        "recommendation": f"Consider batching or parallelizing {len(group)} calls to {service}",
                    })

    # Sort by potential savings
    opportunities.sort(key=lambda x: x.get("potential_savings_ms", 0), reverse=True)
    return opportunities


def _generate_optimization_recommendations(
    critical_path: dict,
    bottleneck: dict | None,
    parallel_opportunities: list,
    span_map: dict,
) -> list[dict[str, Any]]:
    """Generate actionable optimization recommendations."""
    recommendations = []

    # Bottleneck recommendation
    if bottleneck:
        recommendations.append({
            "priority": "HIGH",
            "type": "bottleneck_optimization",
            "target": bottleneck["name"],
            "service": bottleneck.get("service"),
            "current_duration_ms": bottleneck["self_time_ms"],
            "recommendation": (
                f"The span '{bottleneck['name']}' is the primary bottleneck, "
                f"contributing {bottleneck['self_time_ms']:.0f}ms of self-time. "
                f"Focus optimization efforts here for maximum impact."
            ),
            "investigation_steps": [
                "Check if this operation involves database queries",
                "Look for N+1 query patterns",
                "Consider caching frequently accessed data",
                "Profile the code for CPU-intensive operations",
            ],
        })

    # Parallelization recommendations
    if parallel_opportunities:
        top_opportunity = parallel_opportunities[0]
        recommendations.append({
            "priority": "MEDIUM",
            "type": "parallelization",
            "target": top_opportunity.get("service"),
            "current_duration_ms": top_opportunity.get("total_sequential_duration_ms"),
            "potential_duration_ms": top_opportunity.get("potential_parallel_duration_ms"),
            "recommendation": top_opportunity.get("recommendation"),
            "investigation_steps": [
                "Verify spans are truly independent (no data dependencies)",
                "Consider using async/concurrent execution",
                "Look for batch API endpoints",
                "Evaluate if order matters for business logic",
            ],
        })

    # Error span recommendations
    error_spans = [s for s in span_map.values() if s.get("is_error")]
    if error_spans:
        recommendations.append({
            "priority": "HIGH",
            "type": "error_investigation",
            "error_count": len(error_spans),
            "error_services": list(set(s.get("service") for s in error_spans if s.get("service"))),
            "recommendation": (
                f"Found {len(error_spans)} error spans in the trace. "
                "Errors often cause retries and increased latency."
            ),
            "investigation_steps": [
                "Examine error span labels for error messages",
                "Check logs correlated with this trace",
                "Look for timeout or connection errors",
                "Verify downstream service health",
            ],
        })

    # Long span chain recommendation
    if len(critical_path["spans"]) > 5:
        recommendations.append({
            "priority": "LOW",
            "type": "architecture_review",
            "span_depth": len(critical_path["spans"]),
            "recommendation": (
                f"The critical path has {len(critical_path['spans'])} spans deep. "
                "Consider if the call chain can be simplified."
            ),
            "investigation_steps": [
                "Review if intermediate services add value",
                "Consider direct service-to-service calls",
                "Evaluate caching at different layers",
                "Look for unnecessary transformations",
            ],
        })

    return recommendations


@adk_tool
def find_bottleneck_services(
    dataset_id: str,
    table_name: str = "_AllSpans",
    time_window_hours: int = 24,
    min_sample_size: int = 100,
) -> str:
    """
    Identifies services that frequently appear as bottlenecks on critical paths.

    This aggregates across many traces to find systematic bottlenecks,
    not just one-off slow requests.

    Args:
        dataset_id: BigQuery dataset containing trace data
        table_name: Table name containing OTel traces
        time_window_hours: Time window for analysis
        min_sample_size: Minimum number of traces to consider statistically significant

    Returns:
        JSON with SQL query to find bottleneck services
    """
    with tracer.start_as_current_span("find_bottleneck_services") as span:
        critical_path_operations.add(1, {"type": "find_bottlenecks"})

        sql = f"""
-- Find services that frequently appear as bottlenecks
-- by analyzing which services contribute most to trace latency

WITH span_metrics AS (
  SELECT
    trace_id,
    span_id,
    parent_span_id,
    JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') as service_name,
    name as operation_name,
    duration_nano / 1000000 as duration_ms,
    kind,
    status.code as status_code,
    -- Calculate if this is a leaf span (no children)
    NOT EXISTS (
      SELECT 1 FROM `{dataset_id}.{table_name}` child
      WHERE child.parent_span_id = `{dataset_id}.{table_name}`.span_id
        AND child.trace_id = `{dataset_id}.{table_name}`.trace_id
    ) as is_leaf_span
  FROM `{dataset_id}.{table_name}`
  WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)
),
trace_totals AS (
  SELECT
    trace_id,
    SUM(duration_ms) as total_trace_duration_ms,
    COUNT(*) as span_count
  FROM span_metrics
  WHERE parent_span_id IS NULL
  GROUP BY trace_id
  HAVING span_count >= 2  -- Only multi-span traces
),
service_contributions AS (
  SELECT
    sm.service_name,
    sm.operation_name,
    sm.trace_id,
    sm.duration_ms,
    tt.total_trace_duration_ms,
    sm.duration_ms / tt.total_trace_duration_ms * 100 as contribution_pct,
    sm.is_leaf_span,
    CASE WHEN sm.status_code = 2 THEN 1 ELSE 0 END as is_error
  FROM span_metrics sm
  JOIN trace_totals tt ON sm.trace_id = tt.trace_id
  WHERE sm.service_name IS NOT NULL
)
SELECT
  service_name,
  operation_name,
  COUNT(DISTINCT trace_id) as trace_count,
  ROUND(AVG(contribution_pct), 2) as avg_contribution_pct,
  ROUND(APPROX_QUANTILES(contribution_pct, 100)[OFFSET(95)], 2) as p95_contribution_pct,
  ROUND(AVG(duration_ms), 2) as avg_duration_ms,
  ROUND(APPROX_QUANTILES(duration_ms, 100)[OFFSET(95)], 2) as p95_duration_ms,
  COUNTIF(is_leaf_span) as leaf_span_count,
  ROUND(SUM(is_error) / COUNT(*) * 100, 2) as error_rate_pct,
  -- Bottleneck score: high contribution + high latency + frequent occurrence
  ROUND(
    AVG(contribution_pct) * 0.4 +
    (APPROX_QUANTILES(duration_ms, 100)[OFFSET(95)] / 100) * 0.3 +
    (COUNT(DISTINCT trace_id) / {min_sample_size}) * 0.3,
    2
  ) as bottleneck_score
FROM service_contributions
GROUP BY service_name, operation_name
HAVING trace_count >= {min_sample_size}
ORDER BY bottleneck_score DESC
LIMIT 20
"""

        result = {
            "analysis_type": "bottleneck_services",
            "sql_query": sql.strip(),
            "metrics_explained": {
                "avg_contribution_pct": "Average % of trace duration from this service/operation",
                "p95_contribution_pct": "95th percentile contribution (shows worst case)",
                "avg_duration_ms": "Average latency of this operation",
                "p95_duration_ms": "95th percentile latency",
                "leaf_span_count": "Operations at the end of call chains (often real work)",
                "bottleneck_score": "Composite score (higher = more likely bottleneck)",
            },
            "interpretation": {
                "high_contribution_high_latency": "Classic bottleneck - optimize this operation",
                "high_contribution_low_latency": "Called frequently - look for N+1 patterns",
                "high_error_rate": "Errors causing retries and cascading latency",
                "many_leaf_spans": "Actual work happening here, not just orchestration",
            },
            "next_steps": [
                "Execute SQL using BigQuery MCP execute_sql",
                "Focus on top 3 services by bottleneck_score",
                "Use analyze_critical_path on specific traces from these services",
                "Check for N+1 patterns with high call counts",
            ],
        }

        logger.info("Generated bottleneck services analysis SQL")
        return json.dumps(result)


@adk_tool
def calculate_critical_path_contribution(
    dataset_id: str,
    table_name: str = "_AllSpans",
    service_name: str | None = None,
    operation_name: str | None = None,
    time_window_hours: int = 24,
) -> str:
    """
    Calculates how much a specific service/operation contributes to critical paths.

    This helps answer: "If I optimize this service, how much will overall
    latency improve?" - the key question for prioritizing optimization work.

    Args:
        dataset_id: BigQuery dataset containing trace data
        table_name: Table name containing OTel traces
        service_name: Service to analyze
        operation_name: Specific operation to analyze (optional)
        time_window_hours: Time window for analysis

    Returns:
        JSON with SQL query and analysis guidance
    """
    with tracer.start_as_current_span("calculate_critical_path_contribution") as span:
        critical_path_operations.add(1, {"type": "contribution"})

        where_clauses = [
            f"start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_window_hours} HOUR)"
        ]
        if service_name:
            where_clauses.append(
                f"JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') = '{service_name}'"
            )
        if operation_name:
            where_clauses.append(f"name = '{operation_name}'")

        where_clause = " AND ".join(where_clauses)

        sql = f"""
-- Calculate critical path contribution for a specific service/operation
-- This shows the potential latency improvement from optimization

WITH target_spans AS (
  SELECT
    trace_id,
    span_id,
    parent_span_id,
    JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') as service_name,
    name as operation_name,
    start_time,
    end_time,
    duration_nano / 1000000 as duration_ms,
    status.code as status_code
  FROM `{dataset_id}.{table_name}`
  WHERE {where_clause}
),
trace_durations AS (
  SELECT
    trace_id,
    MAX(duration_nano) / 1000000 as trace_duration_ms
  FROM `{dataset_id}.{table_name}`
  WHERE trace_id IN (SELECT DISTINCT trace_id FROM target_spans)
    AND parent_span_id IS NULL
  GROUP BY trace_id
),
contribution_analysis AS (
  SELECT
    ts.trace_id,
    ts.service_name,
    ts.operation_name,
    ts.duration_ms as span_duration_ms,
    td.trace_duration_ms,
    ts.duration_ms / td.trace_duration_ms * 100 as contribution_pct,
    ts.status_code
  FROM target_spans ts
  JOIN trace_durations td ON ts.trace_id = td.trace_id
)
SELECT
  service_name,
  operation_name,
  COUNT(DISTINCT trace_id) as trace_count,
  -- Duration statistics
  ROUND(AVG(span_duration_ms), 2) as avg_span_duration_ms,
  ROUND(APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(50)], 2) as p50_span_duration_ms,
  ROUND(APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(95)], 2) as p95_span_duration_ms,
  ROUND(APPROX_QUANTILES(span_duration_ms, 100)[OFFSET(99)], 2) as p99_span_duration_ms,
  -- Contribution statistics
  ROUND(AVG(contribution_pct), 2) as avg_contribution_pct,
  ROUND(APPROX_QUANTILES(contribution_pct, 100)[OFFSET(50)], 2) as p50_contribution_pct,
  ROUND(APPROX_QUANTILES(contribution_pct, 100)[OFFSET(95)], 2) as p95_contribution_pct,
  -- Trace context
  ROUND(AVG(trace_duration_ms), 2) as avg_trace_duration_ms,
  -- Error rate
  ROUND(COUNTIF(status_code = 2) / COUNT(*) * 100, 2) as error_rate_pct,
  -- Optimization potential
  ROUND(AVG(span_duration_ms) * AVG(contribution_pct) / 100, 2) as weighted_impact_ms
FROM contribution_analysis
GROUP BY service_name, operation_name
ORDER BY weighted_impact_ms DESC
"""

        result = {
            "analysis_type": "critical_path_contribution",
            "target_service": service_name,
            "target_operation": operation_name,
            "sql_query": sql.strip(),
            "metrics_explained": {
                "avg_contribution_pct": "Average % of total trace duration from this span",
                "p95_contribution_pct": "In worst cases, this span uses X% of trace time",
                "weighted_impact_ms": "Expected latency savings if you cut this span's time in half",
            },
            "optimization_formula": (
                "If you reduce span latency by X%, expect trace latency to "
                "reduce by approximately X% * avg_contribution_pct"
            ),
            "next_steps": [
                "Execute SQL using BigQuery MCP execute_sql",
                "Focus on operations with highest weighted_impact_ms",
                "Use analyze_critical_path on specific traces",
                "Look for error_rate_pct > 0 as they often cause retries",
            ],
        }

        logger.info(f"Generated critical path contribution SQL for {service_name}/{operation_name}")
        return json.dumps(result)
