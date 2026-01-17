import json

import pytest

from sre_agent.tools.analysis.trace.patterns import (
    detect_all_sre_patterns,
    detect_cascading_timeout,
    detect_connection_pool_issues,
    detect_retry_storm,
)


@pytest.fixture
def retry_storm_trace():
    return {
        "trace_id": "retry-trace",
        "spans": [
            {
                "span_id": "s1",
                "name": "getData.retry",
                "start_time": "2023-01-01T12:00:00.000Z",
                "end_time": "2023-01-01T12:00:00.100Z",
                "parent_span_id": "root",
            },
            {
                "span_id": "s2",
                "name": "getData.retry",
                "start_time": "2023-01-01T12:00:00.150Z",
                "end_time": "2023-01-01T12:00:00.250Z",
                "parent_span_id": "root",
            },
            {
                "span_id": "s3",
                "name": "getData.retry",
                "start_time": "2023-01-01T12:00:00.350Z",
                "end_time": "2023-01-01T12:00:00.500Z",
                "parent_span_id": "root",
            },
        ],
    }


@pytest.fixture
def cascading_timeout_trace():
    return {
        "trace_id": "timeout-trace",
        "spans": [
            {
                "span_id": "root",
                "name": "gateway",
                "start_time": "2023-01-01T12:00:00.000Z",
                "end_time": "2023-01-01T12:00:01.000Z",
                "labels": {"error.type": "timeout"},
            },
            {
                "span_id": "child",
                "name": "auth-service",
                "parent_span_id": "root",
                "start_time": "2023-01-01T12:00:00.100Z",
                "end_time": "2023-01-01T12:00:00.900Z",
                "labels": {"status": "deadline_exceeded"},
            },
        ],
    }


@pytest.fixture
def connection_pool_trace():
    return {
        "trace_id": "pool-trace",
        "spans": [
            {
                "span_id": "s1",
                "name": "db.acquire_connection",
                "start_time": "2023-01-01T12:00:00.000Z",
                "end_time": "2023-01-01T12:00:00.500Z",
                "labels": {"pool.size": "10", "pool.waiting": "5"},
            }
        ],
    }


def test_detect_retry_storm(retry_storm_trace):
    result = detect_retry_storm(json.dumps(retry_storm_trace))
    assert result["has_retry_storm"] is True
    assert result["patterns_found"] == 1
    assert result["retry_patterns"][0]["retry_count"] == 3
    assert result["retry_patterns"][0]["has_exponential_backoff"] is True


def test_detect_cascading_timeout(cascading_timeout_trace):
    result = detect_cascading_timeout(json.dumps(cascading_timeout_trace))
    assert result["cascade_detected"] is True
    assert len(result["cascade_chains"]) == 1
    assert result["cascade_chains"][0]["chain_length"] == 2


def test_detect_connection_pool_issues(connection_pool_trace):
    result = detect_connection_pool_issues(json.dumps(connection_pool_trace))
    assert result["has_pool_exhaustion"] is True
    assert result["issues_found"] == 1
    assert result["pool_issues"][0]["wait_duration_ms"] == 500.0


def test_detect_all_sre_patterns(retry_storm_trace):
    # This one will run all detectors on the retry_storm_trace
    result = detect_all_sre_patterns(json.dumps(retry_storm_trace))
    assert result["patterns_detected"] >= 1
    assert any(p["pattern_type"] == "retry_storm" for p in result["patterns"])
    assert result["overall_health"] != "healthy"


def test_no_patterns_found():
    trace = {
        "trace_id": "clean-trace",
        "spans": [
            {
                "span_id": "1",
                "name": "healthy-op",
                "start_time": "2023-01-01T12:00:00Z",
                "end_time": "2023-01-01T12:00:00.010Z",
            }
        ],
    }
    result = detect_all_sre_patterns(json.dumps(trace))
    assert result["patterns_detected"] == 0
    assert result["overall_health"] == "healthy"
