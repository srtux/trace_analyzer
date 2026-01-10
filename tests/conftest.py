"""Shared test fixtures for SRE Agent tests."""

import json
import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# Helper Functions
# ============================================================================


def generate_trace_id() -> str:
    """Generate a random 128-bit trace ID as hex string."""
    return uuid.uuid4().hex + uuid.uuid4().hex[:16]


def generate_span_id() -> str:
    """Generate a random 64-bit span ID as hex string."""
    return uuid.uuid4().hex[:16]


def generate_timestamp(
    base_time: datetime | None = None, offset_seconds: int = 0
) -> str:
    """Generate a timestamp in ISO format."""
    if base_time is None:
        base_time = datetime.now(timezone.utc)
    timestamp = base_time + timedelta(seconds=offset_seconds)
    return timestamp.isoformat() + "Z"


# ============================================================================
# Log Entry Fixtures
# ============================================================================


@pytest.fixture
def sample_text_payload_logs() -> list[dict[str, Any]]:
    """Sample log entries with textPayload format."""
    base_time = datetime.now(timezone.utc)
    return [
        {
            "logName": "projects/test-project/logs/application",
            "timestamp": generate_timestamp(base_time, -60),
            "severity": "INFO",
            "textPayload": "User 12345 logged in successfully",
            "resource": {"type": "k8s_container"},
        },
        {
            "logName": "projects/test-project/logs/application",
            "timestamp": generate_timestamp(base_time, -55),
            "severity": "INFO",
            "textPayload": "User 67890 logged in successfully",
            "resource": {"type": "k8s_container"},
        },
        {
            "logName": "projects/test-project/logs/application",
            "timestamp": generate_timestamp(base_time, -50),
            "severity": "ERROR",
            "textPayload": "Connection refused to database-primary:5432",
            "resource": {"type": "k8s_container"},
        },
        {
            "logName": "projects/test-project/logs/application",
            "timestamp": generate_timestamp(base_time, -45),
            "severity": "ERROR",
            "textPayload": "Connection refused to database-primary:5432",
            "resource": {"type": "k8s_container"},
        },
        {
            "logName": "projects/test-project/logs/application",
            "timestamp": generate_timestamp(base_time, -40),
            "severity": "WARNING",
            "textPayload": "Retry attempt 1 for request abc123",
            "resource": {"type": "k8s_container"},
        },
    ]


@pytest.fixture
def sample_json_payload_logs() -> list[dict[str, Any]]:
    """Sample log entries with jsonPayload format."""
    base_time = datetime.now(timezone.utc)
    return [
        {
            "logName": "projects/test-project/logs/structured",
            "timestamp": generate_timestamp(base_time, -60),
            "severity": "INFO",
            "jsonPayload": {
                "message": "Request processed successfully",
                "user_id": "12345",
                "duration_ms": 150,
            },
            "resource": {"type": "k8s_container"},
        },
        {
            "logName": "projects/test-project/logs/structured",
            "timestamp": generate_timestamp(base_time, -55),
            "severity": "ERROR",
            "jsonPayload": {
                "message": "Database connection failed",
                "error_code": "CONN_REFUSED",
                "host": "db-primary",
            },
            "resource": {"type": "k8s_container"},
        },
        {
            "logName": "projects/test-project/logs/structured",
            "timestamp": generate_timestamp(base_time, -50),
            "severity": "INFO",
            "jsonPayload": {
                "msg": "Health check passed",  # Different field name
                "service": "api-gateway",
            },
            "resource": {"type": "k8s_container"},
        },
        {
            "logName": "projects/test-project/logs/structured",
            "timestamp": generate_timestamp(base_time, -45),
            "severity": "ERROR",
            "jsonPayload": {
                "log": "Timeout waiting for response",  # Another field name
                "timeout_ms": 30000,
            },
            "resource": {"type": "k8s_container"},
        },
    ]


@pytest.fixture
def sample_proto_payload_logs() -> list[dict[str, Any]]:
    """Sample log entries with protoPayload format (audit logs)."""
    base_time = datetime.now(timezone.utc)
    return [
        {
            "logName": "projects/test-project/logs/cloudaudit.googleapis.com%2Factivity",
            "timestamp": generate_timestamp(base_time, -60),
            "severity": "NOTICE",
            "protoPayload": {
                "@type": "type.googleapis.com/google.cloud.audit.AuditLog",
                "methodName": "compute.instances.insert",
                "serviceName": "compute.googleapis.com",
                "status": {"message": "Instance created successfully"},
            },
            "resource": {"type": "gce_instance"},
        },
    ]


@pytest.fixture
def baseline_period_logs() -> list[dict[str, Any]]:
    """Log entries from a baseline (healthy) period."""
    base_time = datetime.now(timezone.utc) - timedelta(hours=2)
    logs = []

    # Normal patterns
    for i in range(20):
        logs.append({
            "logName": "projects/test-project/logs/app",
            "timestamp": generate_timestamp(base_time, i * 5),
            "severity": "INFO",
            "textPayload": f"Request {i} completed successfully in 50ms",
            "resource": {"type": "k8s_container"},
        })

    # Occasional warning
    for i in range(3):
        logs.append({
            "logName": "projects/test-project/logs/app",
            "timestamp": generate_timestamp(base_time, 100 + i * 20),
            "severity": "WARNING",
            "textPayload": f"Slow query detected: 200ms for query {i}",
            "resource": {"type": "k8s_container"},
        })

    return logs


@pytest.fixture
def incident_period_logs() -> list[dict[str, Any]]:
    """Log entries from an incident period with new error patterns."""
    base_time = datetime.now(timezone.utc) - timedelta(hours=1)
    logs = []

    # Some normal patterns still exist
    for i in range(10):
        logs.append({
            "logName": "projects/test-project/logs/app",
            "timestamp": generate_timestamp(base_time, i * 5),
            "severity": "INFO",
            "textPayload": f"Request {i} completed successfully in 50ms",
            "resource": {"type": "k8s_container"},
        })

    # NEW ERROR PATTERNS (not in baseline)
    for i in range(15):
        logs.append({
            "logName": "projects/test-project/logs/app",
            "timestamp": generate_timestamp(base_time, 50 + i * 3),
            "severity": "ERROR",
            "textPayload": f"Connection refused to database-primary:5432 (attempt {i})",
            "resource": {"type": "k8s_container"},
        })

    # Another new error pattern
    for i in range(8):
        logs.append({
            "logName": "projects/test-project/logs/app",
            "timestamp": generate_timestamp(base_time, 100 + i * 5),
            "severity": "ERROR",
            "textPayload": f"Timeout waiting for lock on resource {i}",
            "resource": {"type": "k8s_container"},
        })

    # Increased warnings
    for i in range(10):
        logs.append({
            "logName": "projects/test-project/logs/app",
            "timestamp": generate_timestamp(base_time, 150 + i * 5),
            "severity": "WARNING",
            "textPayload": f"Retry attempt {i % 3 + 1} for request {i}",
            "resource": {"type": "k8s_container"},
        })

    return logs


@pytest.fixture
def mixed_payload_logs() -> list[dict[str, Any]]:
    """Mix of different payload types for extraction testing."""
    base_time = datetime.now(timezone.utc)
    return [
        # textPayload
        {
            "timestamp": generate_timestamp(base_time, -60),
            "severity": "INFO",
            "textPayload": "Simple text message",
            "resource": {"type": "k8s_container"},
        },
        # jsonPayload with "message" field
        {
            "timestamp": generate_timestamp(base_time, -55),
            "severity": "INFO",
            "jsonPayload": {"message": "JSON message field", "extra": "data"},
            "resource": {"type": "k8s_container"},
        },
        # jsonPayload with "msg" field
        {
            "timestamp": generate_timestamp(base_time, -50),
            "severity": "INFO",
            "jsonPayload": {"msg": "JSON msg field", "level": "info"},
            "resource": {"type": "k8s_container"},
        },
        # jsonPayload with "log" field
        {
            "timestamp": generate_timestamp(base_time, -45),
            "severity": "INFO",
            "jsonPayload": {"log": "JSON log field", "stream": "stdout"},
            "resource": {"type": "k8s_container"},
        },
        # jsonPayload with nested message
        {
            "timestamp": generate_timestamp(base_time, -40),
            "severity": "INFO",
            "jsonPayload": {
                "data": {"message": "Nested message", "id": 123}
            },
            "resource": {"type": "k8s_container"},
        },
        # protoPayload
        {
            "timestamp": generate_timestamp(base_time, -35),
            "severity": "NOTICE",
            "protoPayload": {
                "@type": "type.googleapis.com/google.cloud.audit.AuditLog",
                "methodName": "storage.objects.create",
                "status": {"message": "Object created"},
            },
            "resource": {"type": "gcs_bucket"},
        },
        # Empty/minimal entry
        {
            "timestamp": generate_timestamp(base_time, -30),
            "severity": "DEBUG",
            "resource": {"type": "k8s_container"},
        },
    ]


# ============================================================================
# Trace Fixtures
# ============================================================================


@pytest.fixture
def sample_trace_spans() -> list[dict[str, Any]]:
    """Sample trace spans for testing."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    child_span_id = generate_span_id()

    return [
        {
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_span_id": None,
            "name": "HTTP GET /api/users",
            "kind": 2,  # SERVER
            "start_time": generate_timestamp(offset_seconds=-1),
            "end_time": generate_timestamp(),
            "status": {"code": 1, "message": ""},
            "attributes": {
                "http.method": "GET",
                "http.status_code": "200",
            },
            "resource": {
                "attributes": {"service.name": "api-gateway"}
            },
        },
        {
            "trace_id": trace_id,
            "span_id": child_span_id,
            "parent_span_id": root_span_id,
            "name": "DB SELECT users",
            "kind": 3,  # CLIENT
            "start_time": generate_timestamp(offset_seconds=-1),
            "end_time": generate_timestamp(),
            "status": {"code": 1, "message": ""},
            "attributes": {
                "db.system": "postgresql",
                "db.operation": "SELECT",
            },
            "resource": {
                "attributes": {"service.name": "api-gateway"}
            },
        },
    ]


# ============================================================================
# Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_logging_client():
    """Mock Cloud Logging client."""
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_trace_client():
    """Mock Cloud Trace client."""
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_bigquery_client():
    """Mock BigQuery client."""
    mock = MagicMock()
    return mock
