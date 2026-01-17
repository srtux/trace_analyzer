"""SRE Pattern Detection - Detects common distributed systems anti-patterns.

This module provides detection for patterns that commonly indicate issues in
distributed systems, helping SREs quickly identify root causes.

Patterns detected:
- Retry storms: Excessive retries indicating downstream issues
- Cascading timeouts: Timeout propagation through service chain
- Connection pool exhaustion: Long waits for connections
- Lock contention: Spans waiting on locks/mutexes (Future)
- Cold start latency: Unusually slow first requests (Future)
- Thundering herd: Many parallel requests to same resource (Future)
"""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

from ...clients.trace import fetch_trace_data
from ...common import adk_tool
from ...common.telemetry import get_meter, get_tracer, log_tool_call

logger = logging.getLogger(__name__)

# Telemetry setup
tracer = get_tracer(__name__)
meter = get_meter(__name__)

# Metrics
execution_duration = meter.create_histogram(
    name="sre_agent.tool.execution_duration",
    description="Duration of tool executions",
    unit="ms",
)
execution_count = meter.create_counter(
    name="sre_agent.tool.execution_count",
    description="Total number of tool calls",
    unit="1",
)
patterns_detected = meter.create_counter(
    name="sre_agent.analysis.patterns_detected",
    description="Count of SRE anti-patterns found",
    unit="1",
)


def _record_telemetry(
    func_name: str, success: bool = True, duration_ms: float = 0.0
) -> None:
    attributes = {
        "code.function": func_name,
        "code.namespace": __name__,
        "success": str(success).lower(),
        "sre_agent.tool.name": func_name,
    }
    execution_count.add(1, attributes)
    execution_duration.record(duration_ms, attributes)


# Pattern indicator keywords in span names and labels
RETRY_INDICATORS = ["retry", "attempt", "backoff", "reconnect"]
TIMEOUT_INDICATORS = [
    "timeout",
    "deadline",
    "exceeded",
    "timed out",
    "context deadline",
]
CONNECTION_INDICATORS = ["connection", "pool", "acquire", "checkout", "wait"]


def _parse_timestamp(ts: str) -> float | None:
    """Parse ISO timestamp to milliseconds since epoch."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000
    except (ValueError, TypeError):
        return None


def _get_span_duration(span: dict[str, Any]) -> float | None:
    """Get span duration in milliseconds."""
    if "duration_ms" in span:
        return float(span["duration_ms"])

    start = _parse_timestamp(span.get("start_time", ""))
    end = _parse_timestamp(span.get("end_time", ""))
    if start and end:
        return end - start
    return None


def _contains_indicator(text: str, indicators: list[str]) -> bool:
    """Check if text contains any of the indicator keywords."""
    text_lower = text.lower()
    return any(ind in text_lower for ind in indicators)


def _extract_span_info(span: dict[str, Any]) -> dict[str, Any]:
    """Extract key info from a span for pattern reporting."""
    return {
        "span_id": span.get("span_id"),
        "span_name": span.get("name"),
        "duration_ms": _get_span_duration(span),
        "parent_span_id": span.get("parent_span_id"),
        "labels": span.get("labels", {}),
    }


@adk_tool
def detect_retry_storm(
    trace_id: str, project_id: str | None = None, threshold: int = 3
) -> dict[str, Any]:
    """Detect retry storm patterns in a trace.

    A retry storm occurs when a service makes multiple retry attempts,
    often indicating an unhealthy downstream dependency. This can
    amplify load and create cascading failures.

    Args:
        trace_id: The trace ID to analyze.
        project_id: The Google Cloud Project ID.
        threshold: Minimum retry count to flag as a storm (default: 3).

    Returns:
        Detection results with retry patterns found.
    """
    import time

    start_time = time.time()
    success = True

    with tracer.start_as_current_span("detect_retry_storm") as span:
        log_tool_call(logger, "detect_retry_storm", trace_id=trace_id)

        try:
            trace = fetch_trace_data(trace_id, project_id)
            if "error" in trace:
                return {"error": trace["error"]}

            spans = trace.get("spans", [])
            retry_patterns = []

            # Group spans by name to find repeated operations
            spans_by_name = defaultdict(list)
            for s in spans:
                name = s.get("name", "")
                spans_by_name[name].append(s)

            for name, span_list in spans_by_name.items():
                # Check if name contains retry indicators
                is_retry_span = _contains_indicator(name, RETRY_INDICATORS)

                # Or check if we have many sequential spans with the same name
                if len(span_list) >= threshold or is_retry_span:
                    # Sort by start time
                    sorted_spans = sorted(
                        span_list,
                        key=lambda s: _parse_timestamp(s.get("start_time", "")) or 0,
                    )

                    # Check for sequential pattern (small gaps between spans)
                    sequential_count = 1
                    for i in range(1, len(sorted_spans)):
                        prev_end = _parse_timestamp(
                            sorted_spans[i - 1].get("end_time", "")
                        )
                        curr_start = _parse_timestamp(
                            sorted_spans[i].get("start_time", "")
                        )
                        if prev_end and curr_start:
                            gap_ms = curr_start - prev_end
                            # If gap is small (< 1 second), likely retries
                            if 0 <= gap_ms < 1000:
                                sequential_count += 1

                    if sequential_count >= threshold or is_retry_span:
                        total_duration = sum(
                            _get_span_duration(s) or 0 for s in span_list
                        )

                        # Check for exponential backoff pattern
                        durations = [_get_span_duration(s) or 0 for s in sorted_spans]
                        has_backoff = False
                        if len(durations) >= 3:
                            # Check if durations are increasing (backoff pattern)
                            increasing = all(
                                durations[i] <= durations[i + 1] * 1.5
                                for i in range(len(durations) - 1)
                            )
                            has_backoff = increasing

                        retry_patterns.append(
                            {
                                "pattern_type": "retry_storm",
                                "span_name": name,
                                "retry_count": len(span_list),
                                "total_duration_ms": round(total_duration, 2),
                                "has_exponential_backoff": has_backoff,
                                "impact": "high" if len(span_list) >= 5 else "medium",
                                "recommendation": (
                                    "Investigate downstream service health. "
                                    "Consider circuit breaker pattern if not implemented."
                                ),
                            }
                        )

            patterns_detected.add(len(retry_patterns), {"type": "retry_storm"})
            return {
                "trace_id": trace_id,
                "patterns_found": len(retry_patterns),
                "retry_patterns": retry_patterns,
                "has_retry_storm": len(retry_patterns) > 0,
            }

        except Exception as e:
            span.record_exception(e)
            success = False
            raise e
        finally:
            duration_ms = (time.time() - start_time) * 1000
            _record_telemetry("detect_retry_storm", success, duration_ms)


@adk_tool
def detect_cascading_timeout(
    trace_id: str, project_id: str | None = None, timeout_threshold_ms: float = 1000
) -> dict[str, Any]:
    """Detect cascading timeout patterns in a trace.

    Cascading timeouts occur when a timeout in one service causes
    timeouts to propagate up the call chain. This is often caused
    by insufficient timeout budgeting.

    Args:
        trace_id: The trace ID to analyze.
        project_id: The Google Cloud Project ID.
        timeout_threshold_ms: Minimum duration to consider as potential timeout.

    Returns:
        Detection results with timeout cascade information.
    """
    import time

    start_time = time.time()
    success = True

    with tracer.start_as_current_span("detect_cascading_timeout") as span:
        log_tool_call(logger, "detect_cascading_timeout", trace_id=trace_id)

        try:
            trace = fetch_trace_data(trace_id, project_id)
            if "error" in trace:
                return {"error": trace["error"]}

            spans = trace.get("spans", [])
            timeout_spans = []

            # Find spans that look like timeouts
            for s in spans:
                name = s.get("name", "")
                labels = s.get("labels", {})
                labels_str = str(labels).lower()

                is_timeout = (
                    _contains_indicator(name, TIMEOUT_INDICATORS)
                    or _contains_indicator(labels_str, TIMEOUT_INDICATORS)
                    or labels.get("error.type") == "timeout"
                    or "deadline" in labels_str
                )

                duration = _get_span_duration(s) or 0

                if is_timeout or duration >= timeout_threshold_ms:
                    timeout_spans.append(
                        {
                            **_extract_span_info(s),
                            "is_explicit_timeout": is_timeout,
                            "start_ms": _parse_timestamp(s.get("start_time", "")),
                        }
                    )

            # Sort by start time to detect cascade
            timeout_spans.sort(key=lambda s: s.get("start_ms") or 0)

            # Detect cascade: child times out, then parent times out
            cascade_chains: list[dict[str, Any]] = []
            if len(timeout_spans) >= 2:
                # Build parent-child relationships
                parent_map = {s.get("span_id"): s.get("parent_span_id") for s in spans}

                # Check for timeout propagation chains
                for timeout_span in timeout_spans:
                    chain = [timeout_span]
                    current_id = timeout_span.get("parent_span_id")

                    # Walk up the tree looking for parent timeouts
                    while current_id:
                        parent_timeout = next(
                            (
                                t
                                for t in timeout_spans
                                if t.get("span_id") == current_id
                            ),
                            None,
                        )
                        if parent_timeout:
                            chain.append(parent_timeout)
                        current_id = parent_map.get(current_id)

                    if len(chain) >= 2:
                        cascade_chains.append(
                            {
                                "chain_length": len(chain),
                                "origin_span": chain[0]["span_name"],
                                "affected_spans": [c["span_name"] for c in chain],
                                "total_timeout_duration_ms": sum(
                                    c.get("duration_ms") or 0 for c in chain
                                ),
                            }
                        )

            # Remove duplicate chains (subsets of longer chains)
            unique_chains: list[dict[str, Any]] = []
            for c in sorted(
                cascade_chains, key=lambda ch: ch["chain_length"], reverse=True
            ):
                affected = set(c["affected_spans"])
                is_subset = any(
                    affected <= set(uc["affected_spans"]) for uc in unique_chains
                )
                if not is_subset:
                    unique_chains.append(c)

            patterns_detected.add(len(unique_chains), {"type": "cascading_timeout"})
            return {
                "trace_id": trace_id,
                "timeout_spans_count": len(timeout_spans),
                "timeout_spans": timeout_spans[:10],  # Limit output
                "cascade_detected": len(unique_chains) > 0,
                "cascade_chains": unique_chains,
                "impact": "critical" if len(unique_chains) > 0 else "low",
                "recommendation": (
                    "Review timeout configuration. Consider deadline propagation "
                    "and ensure child timeouts are shorter than parent timeouts."
                    if unique_chains
                    else "No cascading timeout detected."
                ),
            }

        except Exception as e:
            span.record_exception(e)
            success = False
            raise e
        finally:
            duration_ms = (time.time() - start_time) * 1000
            _record_telemetry("detect_cascading_timeout", success, duration_ms)


@adk_tool
def detect_connection_pool_issues(
    trace_id: str, project_id: str | None = None, wait_threshold_ms: float = 100
) -> dict[str, Any]:
    """Detect connection pool exhaustion or contention patterns.

    Connection pool issues occur when requests wait too long to acquire
    database or HTTP connections, often indicating pool size is too small
    or connections are being held too long.

    Args:
        trace_id: The trace ID to analyze.
        project_id: The Google Cloud Project ID.
        wait_threshold_ms: Threshold for connection wait time to flag.

    Returns:
        Detection results with connection pool issue indicators.
    """
    import time

    start_time = time.time()
    success = True

    with tracer.start_as_current_span("detect_connection_pool_issues") as span:
        log_tool_call(logger, "detect_connection_pool_issues", trace_id=trace_id)

        try:
            trace = fetch_trace_data(trace_id, project_id)
            if "error" in trace:
                return {"error": trace["error"]}

            spans = trace.get("spans", [])
            pool_issues = []

            for s in spans:
                name = s.get("name", "")
                labels = s.get("labels", {})

                # Check for connection-related spans
                if not _contains_indicator(name, CONNECTION_INDICATORS):
                    continue

                duration = _get_span_duration(s) or 0

                # Check for long waits
                if duration >= wait_threshold_ms:
                    # Look for specific pool metrics in labels
                    pool_size = labels.get("pool.size") or labels.get("db.pool_size")
                    active_connections = labels.get("pool.active") or labels.get(
                        "db.active_connections"
                    )
                    waiting = labels.get("pool.waiting") or labels.get(
                        "db.waiting_requests"
                    )

                    pool_issues.append(
                        {
                            "span_name": name,
                            "wait_duration_ms": round(duration, 2),
                            "pool_size": pool_size,
                            "active_connections": active_connections,
                            "waiting_requests": waiting,
                            "severity": (
                                "high"
                                if duration >= wait_threshold_ms * 5
                                else "medium"
                                if duration >= wait_threshold_ms * 2
                                else "low"
                            ),
                        }
                    )

            # Calculate overall impact
            total_wait = sum(p["wait_duration_ms"] for p in pool_issues)

            patterns_detected.add(len(pool_issues), {"type": "connection_pool_issue"})
            return {
                "trace_id": trace_id,
                "issues_found": len(pool_issues),
                "pool_issues": pool_issues,
                "total_wait_ms": round(total_wait, 2),
                "has_pool_exhaustion": len(pool_issues) > 0
                and total_wait >= wait_threshold_ms * 3,
                "recommendation": (
                    "Consider increasing connection pool size or reducing connection hold time. "
                    "Review connection lifecycle and ensure proper connection release."
                    if pool_issues
                    else "No connection pool issues detected."
                ),
            }

        except Exception as e:
            span.record_exception(e)
            success = False
            raise e
        finally:
            duration_ms = (time.time() - start_time) * 1000
            _record_telemetry("detect_connection_pool_issues", success, duration_ms)


@adk_tool
def detect_all_sre_patterns(
    trace_id: str, project_id: str | None = None
) -> dict[str, Any]:
    """Run all SRE pattern detection checks on a trace.

    This is a comprehensive scan that checks for:
    - Retry storms
    - Cascading timeouts
    - Connection pool issues

    Args:
        trace_id: The trace ID to analyze.
        project_id: The Google Cloud Project ID.

    Returns:
        Comprehensive pattern detection results.
    """
    import time

    start_time = time.time()
    success = True

    with tracer.start_as_current_span("detect_all_sre_patterns") as span:
        log_tool_call(logger, "detect_all_sre_patterns", trace_id=trace_id)

        try:
            # Run all detectors (using internal logic to avoid double-fetching)
            results: dict[str, Any] = {
                "trace_id": trace_id,
                "patterns": [],
                "overall_health": "healthy",
                "recommendations": [],
            }

            # Retry storm detection
            retry_result = detect_retry_storm(trace_id, project_id)
            if retry_result.get("has_retry_storm"):
                results["patterns"].extend(retry_result["retry_patterns"])
                results["recommendations"].append(
                    {
                        "pattern": "retry_storm",
                        "action": "Investigate downstream service health and implement circuit breakers",
                    }
                )

            # Cascading timeout detection
            timeout_result = detect_cascading_timeout(trace_id, project_id)
            if timeout_result.get("cascade_detected"):
                results["patterns"].append(
                    {
                        "pattern_type": "cascading_timeout",
                        "chains": timeout_result["cascade_chains"],
                        "impact": timeout_result["impact"],
                    }
                )
                results["recommendations"].append(
                    {
                        "pattern": "cascading_timeout",
                        "action": "Review timeout configuration and implement deadline propagation",
                    }
                )

            # Connection pool detection
            pool_result = detect_connection_pool_issues(trace_id, project_id)
            if pool_result.get("has_pool_exhaustion"):
                results["patterns"].append(
                    {
                        "pattern_type": "connection_pool_exhaustion",
                        "issues": pool_result["pool_issues"],
                        "total_wait_ms": pool_result["total_wait_ms"],
                    }
                )
                results["recommendations"].append(
                    {
                        "pattern": "connection_pool_exhaustion",
                        "action": "Increase pool size or optimize connection lifecycle",
                    }
                )

            # Determine overall health
            if any(p.get("impact") == "critical" for p in results["patterns"]):
                results["overall_health"] = "critical"
            elif any(
                p.get("impact") == "high"
                for p in results["patterns"]
                if isinstance(p.get("impact"), str)
            ):
                results["overall_health"] = "degraded"
            elif results["patterns"]:
                results["overall_health"] = "warning"

            results["patterns_detected"] = len(results["patterns"])

            return results

        except Exception as e:
            span.record_exception(e)
            success = False
            raise e
        finally:
            duration_ms = (time.time() - start_time) * 1000
            _record_telemetry("detect_all_sre_patterns", success, duration_ms)
