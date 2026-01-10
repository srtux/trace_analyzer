"""Synthetic OpenTelemetry test data generators.

This module provides factories for generating realistic OTel trace data
for testing purposes, following the Google Cloud Observability schema.
"""

import random
import string
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


def generate_trace_id() -> str:
    """Generate a random 128-bit trace ID as hex string."""
    return uuid.uuid4().hex + uuid.uuid4().hex[:16]


def generate_span_id() -> str:
    """Generate a random 64-bit span ID as hex string."""
    return uuid.uuid4().hex[:16]


def generate_timestamp(
    base_time: datetime | None = None, offset_seconds: float = 0
) -> str:
    """Generate a timestamp in ISO format."""
    if base_time is None:
        base_time = datetime.now(timezone.utc)
    timestamp = base_time + timedelta(seconds=offset_seconds)
    # Ensure simplified ISO format with Z suffix for compatibility
    return timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def generate_random_string(length: int = 10) -> str:
    """Generate a random alphanumeric string."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


@dataclass
class SpanEventGenerator:
    """Generator for span events (exceptions, logs, etc.)."""

    @staticmethod
    def exception_event(
        exception_type: str = "ValueError",
        exception_message: str = "Invalid input",
        timestamp: str | None = None,
        include_stacktrace: bool = True,
    ) -> dict[str, Any]:
        """Generate an exception event."""
        if timestamp is None:
            timestamp = generate_timestamp()

        attributes = {
            "exception.type": exception_type,
            "exception.message": exception_message,
        }

        if include_stacktrace:
            attributes["exception.stacktrace"] = f"""Traceback (most recent call last):
  File "main.py", line 42, in process_request
    result = validate_input(data)
  File "validator.py", line 15, in validate_input
    raise {exception_type}("{exception_message}")
{exception_type}: {exception_message}"""

        return {"name": "exception", "time": timestamp, "attributes": attributes}

    @staticmethod
    def log_event(
        message: str = "Processing completed",
        severity: str = "INFO",
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Generate a log event."""
        if timestamp is None:
            timestamp = generate_timestamp()

        return {
            "name": "log",
            "time": timestamp,
            "attributes": {"log.message": message, "log.severity": severity},
        }


@dataclass
class SpanLinkGenerator:
    """Generator for span links."""

    @staticmethod
    def create_link(
        linked_trace_id: str | None = None,
        linked_span_id: str | None = None,
        link_type: str = "follows_from",
        reason: str = "async_dependency",
    ) -> dict[str, Any]:
        """Generate a span link."""
        if linked_trace_id is None:
            linked_trace_id = generate_trace_id()
        if linked_span_id is None:
            linked_span_id = generate_span_id()

        return {
            "trace_id": linked_trace_id,
            "span_id": linked_span_id,
            "trace_state": "",
            "attributes": {"link.type": link_type, "link.reason": reason},
        }

    @staticmethod
    def batch_link(batch_id: str | None = None) -> dict[str, Any]:
        """Generate a link to a batch processing job."""
        return SpanLinkGenerator.create_link(
            link_type="batch",
            reason=f"batch_job_{batch_id or generate_random_string(8)}",
        )

    @staticmethod
    def async_link() -> dict[str, Any]:
        """Generate a link for async operation."""
        return SpanLinkGenerator.create_link(
            link_type="async", reason="async_operation"
        )


@dataclass
class OtelSpanGenerator:
    """Generator for complete OTel spans."""

    service_name: str = "test-service"
    trace_id: str = field(default_factory=generate_trace_id)
    parent_span_id: str | None = None
    base_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def create_span(
        self,
        name: str = "test-operation",
        kind: int = 2,  # SERVER
        duration_ms: float = 100.0,
        status_code: int = 1,  # OK
        status_message: str = "",
        http_method: str | None = None,
        http_status_code: int | None = None,
        http_target: str | None = None,
        db_system: str | None = None,
        db_operation: str | None = None,
        events: list[dict] | None = None,
        links: list[dict] | None = None,
        instrumentation_name: str = "opentelemetry.instrumentation.test",
        instrumentation_version: str = "1.0.0",
        custom_attributes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a complete OTel span."""
        span_id = generate_span_id()
        start_time = generate_timestamp(self.base_time)
        duration_nano = int(duration_ms * 1_000_000)
        end_time = generate_timestamp(
            self.base_time, offset_seconds=duration_ms / 1000.0
        )

        # Build attributes
        attributes = custom_attributes or {}

        if http_method:
            attributes["http.method"] = http_method
        if http_status_code:
            attributes["http.status_code"] = str(http_status_code)
        if http_target:
            attributes["http.target"] = http_target
            attributes["http.url"] = (
                f"https://{self.service_name}.example.com{http_target}"
            )

        if db_system:
            attributes["db.system"] = db_system
        if db_operation:
            attributes["db.operation"] = db_operation

        # Build resource attributes
        resource_attributes = {
            "service.name": self.service_name,
            "service.version": "1.0.0",
            "host.name": f"host-{generate_random_string(5)}",
            "cloud.provider": "gcp",
            "cloud.region": "us-central1",
        }

        span = {
            "trace_id": self.trace_id,
            "span_id": span_id,
            "trace_state": "",
            "parent_span_id": self.parent_span_id,
            "name": name,
            "kind": kind,
            "start_time": start_time,
            "end_time": end_time,
            "duration_nano": duration_nano,
            "attributes": attributes,
            "status": {"code": status_code, "message": status_message},
            "events": events or [],
            "links": links or [],
            "resource": {"attributes": resource_attributes},
            "instrumentation_scope": {
                "name": instrumentation_name,
                "version": instrumentation_version,
                "schema_url": "https://opentelemetry.io/schemas/1.20.0",
            },
        }

        return span

    def create_http_server_span(
        self,
        endpoint: str = "/api/users",
        method: str = "GET",
        status_code: int = 200,
        duration_ms: float = 50.0,
        include_error: bool = False,
    ) -> dict[str, Any]:
        """Generate an HTTP server span."""
        span_status_code = 2 if include_error else 1  # ERROR or OK
        status_message = "Internal server error" if include_error else ""

        events = []
        if include_error:
            events.append(
                SpanEventGenerator.exception_event(
                    exception_type="InternalError",
                    exception_message="Database connection failed",
                    timestamp=generate_timestamp(
                        self.base_time, offset_seconds=int(duration_ms / 2000)
                    ),
                )
            )

        return self.create_span(
            name=f"HTTP {method} {endpoint}",
            kind=2,  # SERVER
            duration_ms=duration_ms,
            status_code=span_status_code,
            status_message=status_message,
            http_method=method,
            http_status_code=status_code if not include_error else 500,
            http_target=endpoint,
            events=events,
        )

    def create_database_span(
        self,
        operation: str = "SELECT",
        table: str = "users",
        duration_ms: float = 25.0,
        db_system: str = "postgresql",
        include_error: bool = False,
    ) -> dict[str, Any]:
        """Generate a database client span."""
        span_status_code = 2 if include_error else 1
        status_message = "Connection timeout" if include_error else ""

        attributes = {
            "db.statement": f"{operation} * FROM {table} WHERE id = $1",
            "db.name": "production_db",
        }

        return self.create_span(
            name=f"DB {operation} {table}",
            kind=3,  # CLIENT
            duration_ms=duration_ms,
            status_code=span_status_code,
            status_message=status_message,
            db_system=db_system,
            db_operation=operation,
            custom_attributes=attributes,
        )

    def create_linked_span(
        self, linked_trace_ids: list[str] | None = None, num_links: int = 1
    ) -> dict[str, Any]:
        """Generate a span with links to other traces."""
        links = []
        if linked_trace_ids:
            for trace_id in linked_trace_ids:
                links.append(SpanLinkGenerator.create_link(linked_trace_id=trace_id))
        else:
            for _ in range(num_links):
                links.append(SpanLinkGenerator.async_link())

        return self.create_span(
            name="async-operation",
            kind=1,  # INTERNAL
            duration_ms=75.0,
            links=links,
        )


@dataclass
class TraceGenerator:
    """Generator for complete traces with multiple spans."""

    service_name: str = "test-service"
    base_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def create_simple_http_trace(
        self,
        endpoint: str = "/api/users",
        include_db_call: bool = True,
        include_error: bool = False,
    ) -> list[dict[str, Any]]:
        """Generate a simple HTTP trace with optional database call."""
        trace_id = generate_trace_id()
        spans = []

        # Create span generator
        generator = OtelSpanGenerator(
            service_name=self.service_name, trace_id=trace_id, base_time=self.base_time
        )

        # Root HTTP span
        http_span = generator.create_http_server_span(
            endpoint=endpoint,
            method="GET",
            duration_ms=100.0 if include_db_call else 50.0,
            include_error=include_error,
        )
        spans.append(http_span)

        # Child database span
        if include_db_call:
            db_generator = OtelSpanGenerator(
                service_name=self.service_name,
                trace_id=trace_id,
                parent_span_id=http_span["span_id"],
                base_time=self.base_time + timedelta(milliseconds=10),
            )
            db_span = db_generator.create_database_span(
                operation="SELECT",
                table="users",
                duration_ms=25.0,
                include_error=include_error,
            )
            spans.append(db_span)

        return spans

    def create_fanout_trace(
        self,
        root_service: str = "api-gateway",
        child_services: list[str] | None = None,
        fanout_degree: int = 3,
        include_errors: bool = False,
    ) -> list[dict[str, Any]]:
        """Generate a trace where one service calls multiple others in parallel."""
        if child_services is None:
            child_services = ["service-a", "service-b", "service-c"]

        trace_id = generate_trace_id()
        spans = []

        # Root Span
        root_gen = OtelSpanGenerator(
            service_name=root_service, trace_id=trace_id, base_time=self.base_time
        )
        root_span = root_gen.create_http_server_span(
            endpoint="/api/fanout", duration_ms=150.0, include_error=False
        )
        spans.append(root_span)

        # Fanout Children
        for i in range(fanout_degree):
            service_name = child_services[i % len(child_services)]
            child_gen = OtelSpanGenerator(
                service_name=service_name,
                trace_id=trace_id,
                parent_span_id=root_span["span_id"],
                base_time=self.base_time + timedelta(milliseconds=20),
            )

            # Make one specific child error if requested
            is_error = include_errors and i == 0

            child_span = child_gen.create_http_server_span(
                endpoint=f"/api/{service_name}",
                duration_ms=50.0 + (i * 10),
                include_error=is_error,
            )
            spans.append(child_span)

        return spans

    def create_async_trace(
        self, service_chain: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Generate a trace with async span links between disjoint traces."""
        if service_chain is None:
            service_chain = ["producer", "consumer"]

        producer_trace_id = generate_trace_id()
        consumer_trace_id = generate_trace_id()

        spans = []

        # 1. Producer Trace
        prod_gen = OtelSpanGenerator(
            service_name=service_chain[0],
            trace_id=producer_trace_id,
            base_time=self.base_time,
        )
        prod_span = prod_gen.create_http_server_span(
            endpoint="/publish", duration_ms=30.0
        )
        spans.append(prod_span)

        # 2. Consumer Trace (linked to producer)
        cons_gen = OtelSpanGenerator(
            service_name=service_chain[1],
            trace_id=consumer_trace_id,
            base_time=self.base_time + timedelta(seconds=2),  # 2s later
        )

        link = SpanLinkGenerator.create_link(
            linked_trace_id=producer_trace_id,
            linked_span_id=prod_span["span_id"],
            link_type="follows_from",
            reason="async_message_processing",
        )

        cons_span = cons_gen.create_span(
            name="process_message",
            kind=1,  # INTERNAL
            duration_ms=100.0,
            links=[link],
        )
        spans.append(cons_span)

        return spans

    def create_multi_service_trace(
        self,
        services: list[str] | None = None,
        include_errors: bool = False,
        latency_strategy: str = "normal",  # normal, creep, spike
    ) -> list[dict[str, Any]]:
        """Generate a trace spanning multiple services."""
        if services is None:
            services = ["frontend", "api-gateway", "user-service", "database"]

        trace_id = generate_trace_id()
        spans = []
        parent_id = None
        current_time = self.base_time

        for i, service in enumerate(services):
            generator = OtelSpanGenerator(
                service_name=service,
                trace_id=trace_id,
                parent_span_id=parent_id,
                base_time=current_time,
            )

            is_last = i == len(services) - 1
            include_error = include_errors and is_last

            # Calculate duration based on strategy
            base_duration = 50.0 + (i * 10)
            if latency_strategy == "spike" and service == "database":
                base_duration *= 10
            elif latency_strategy == "creep":
                base_duration *= 1.5**i

            if service == "database":
                span = generator.create_database_span(
                    operation="SELECT",
                    table="users",
                    duration_ms=base_duration,
                    include_error=include_error,
                )
            else:
                span = generator.create_http_server_span(
                    endpoint="/api/users" if service != "frontend" else "/users",
                    method="GET",
                    duration_ms=base_duration,
                    include_error=include_error,
                )

            spans.append(span)
            parent_id = span["span_id"]
            current_time = current_time + timedelta(milliseconds=10)

        return spans


class BigQueryResultGenerator:
    """Generator for BigQuery MCP response data."""

    @staticmethod
    def aggregate_metrics_result(
        services: list[str] | None = None, with_errors: bool = False
    ) -> list[dict[str, Any]]:
        """Generate mock BigQuery aggregate metrics results."""
        if services is None:
            services = ["frontend", "api-gateway", "user-service"]

        results = []
        for service in services:
            error_rate = (
                random.uniform(0, 5) if not with_errors else random.uniform(10, 25)
            )
            results.append(
                {
                    "service_name": service,
                    "request_count": random.randint(1000, 10000),
                    "error_count": int(random.randint(1000, 10000) * error_rate / 100),
                    "error_rate_pct": round(error_rate, 2),
                    "p50_ms": round(random.uniform(20, 50), 2),
                    "p95_ms": round(random.uniform(100, 300), 2),
                    "p99_ms": round(random.uniform(300, 800), 2),
                    "avg_duration_ms": round(random.uniform(30, 100), 2),
                    "first_seen": generate_timestamp(
                        datetime.now(timezone.utc) - timedelta(hours=24)
                    ),
                    "last_seen": generate_timestamp(),
                }
            )

        return results

    @staticmethod
    def time_series_metrics_result(
        services: list[str] | None = None,
        duration_hours: int = 24,
        interval_minutes: int = 60,
    ) -> list[dict[str, Any]]:
        """Generate mock BigQuery time-series metrics results."""
        if services is None:
            services = ["frontend", "api-gateway", "user-service"]

        results = []

        # Calculate number of points
        num_points = int((duration_hours * 60) / interval_minutes)
        base_time = datetime.now(timezone.utc) - timedelta(hours=duration_hours)

        for service in services:
            # Generate a consistent pattern for each service
            # e.g., sine wave for request count, random spikes for errors
            random.randint(0, 10)

            for i in range(num_points):
                point_time = base_time + timedelta(minutes=i * interval_minutes)

                # Sinusoidal traffic pattern
                traffic_factor = 1.0 + 0.5 * (i % 24 - 12) / 12.0  # Daily cycle roughly
                request_count = int(1000 * traffic_factor)

                # Random error spikes
                is_spike = random.random() > 0.95
                error_count = int(request_count * (0.1 if is_spike else 0.01))

                results.append(
                    {
                        "service_name": service,
                        "time_interval": point_time.isoformat(),
                        "request_count": request_count,
                        "error_count": error_count,
                        "avg_latency": 100
                        + (50 if is_spike else 0)
                        + random.randint(-10, 10),
                    }
                )

        return results

    @staticmethod
    def exemplar_traces_result(
        count: int = 5, strategy: str = "outliers"
    ) -> list[dict[str, Any]]:
        """Generate mock BigQuery exemplar traces results."""
        results = []
        for i in range(count):
            result = {
                "trace_id": generate_trace_id(),
                "operation": f"HTTP GET /api/endpoint{i}",
                "service_name": random.choice(
                    ["frontend", "api-gateway", "user-service"]
                ),
                "duration_ms": round(random.uniform(100, 800), 2),
                "status_code": 2
                if strategy == "errors"
                else random.choice([1, 1, 1, 2]),
                "start_time": generate_timestamp(
                    datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 24))
                ),
                "selection_reason": strategy,
            }

            if strategy == "outliers":
                result["pct_above_p95"] = round(random.uniform(50, 200), 2)
            elif strategy == "errors":
                result["error_message"] = random.choice(
                    [
                        "Connection timeout",
                        "Internal server error",
                        "Database unavailable",
                    ]
                )

            results.append(result)

        return results

    @staticmethod
    def exception_events_result(count: int = 10) -> list[dict[str, Any]]:
        """Generate mock exception events results."""
        exception_types = [
            "ValueError",
            "ConnectionError",
            "TimeoutError",
            "DatabaseError",
            "AuthenticationError",
        ]

        results = []
        for _ in range(count):
            exc_type = random.choice(exception_types)
            results.append(
                {
                    "trace_id": generate_trace_id(),
                    "span_id": generate_span_id(),
                    "span_name": random.choice(
                        [
                            "HTTP GET /api/users",
                            "DB SELECT users",
                            "AUTH validate_token",
                        ]
                    ),
                    "service_name": random.choice(
                        ["frontend", "api-gateway", "user-service"]
                    ),
                    "event_name": "exception",
                    "event_time": generate_timestamp(
                        datetime.now(timezone.utc)
                        - timedelta(hours=random.randint(1, 24))
                    ),
                    "exception_type": exc_type,
                    "exception_message": f"Sample {exc_type} message",
                    "exception_stacktrace": f"Traceback...\n{exc_type}: Sample error",
                }
            )

        return results


class CloudTraceAPIGenerator:
    """Generator for Cloud Trace API response data."""

    @staticmethod
    def trace_response(
        trace_id: str | None = None, include_error: bool = False
    ) -> dict[str, Any]:
        """Generate a mock Cloud Trace API response."""
        if trace_id is None:
            trace_id = generate_trace_id()

        generator = TraceGenerator()
        spans = generator.create_simple_http_trace(
            endpoint="/api/users", include_db_call=True, include_error=include_error
        )

        return {
            "projectId": "test-project",
            "traceId": trace_id,
            "spans": [
                {
                    "spanId": span["span_id"],
                    "kind": span["kind"],
                    "name": span["name"],
                    "startTime": span["start_time"],
                    "endTime": span["end_time"],
                    "parentSpanId": span.get("parent_span_id"),
                    "labels": span.get("attributes", {}),
                }
                for span in spans
            ],
        }

    @staticmethod
    def list_traces_response(count: int = 10) -> dict[str, Any]:
        """Generate a mock list traces response."""
        traces = []
        for _ in range(count):
            traces.append(
                {
                    "projectId": "test-project",
                    "traceId": generate_trace_id(),
                    "spans": [
                        {
                            "spanId": generate_span_id(),
                            "name": random.choice(
                                ["HTTP GET /api/users", "DB SELECT", "CACHE GET"]
                            ),
                            "startTime": generate_timestamp(
                                datetime.now(timezone.utc)
                                - timedelta(hours=random.randint(1, 24))
                            ),
                            "endTime": generate_timestamp(),
                        }
                    ],
                }
            )

        return {"traces": traces}


class CloudLoggingAPIGenerator:
    """Generator for Cloud Logging API response data."""

    @staticmethod
    def create_structured_log_entry(
        message: str,
        payload: dict[str, Any],
        severity: str = "INFO",
        timestamp: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate a structured log entry with jsonPayload."""
        if timestamp is None:
            timestamp = generate_timestamp()

        return {
            "logName": "projects/test-project/logs/application",
            "resource": {
                "type": "k8s_container",
                "labels": {
                    "pod_name": f"pod-{generate_random_string(5)}",
                    "namespace_name": "default",
                },
            },
            "jsonPayload": payload,
            "timestamp": timestamp,
            "severity": severity,
            "trace": f"projects/test-project/traces/{trace_id or generate_trace_id()}",
            "labels": {"service": "test-service"},
        }

    @staticmethod
    def log_entries_response(
        count: int = 10,
        trace_id: str | None = None,
        severity: str = "ERROR",
        json_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate mock Cloud Logging API response."""
        entries = []
        for i in range(count):
            if json_payload:
                entry = CloudLoggingAPIGenerator.create_structured_log_entry(
                    message=f"Log {i}",
                    payload=json_payload,
                    severity=severity,
                    trace_id=trace_id,
                )
            else:
                entry = {
                    "logName": "projects/test-project/logs/application",
                    "resource": {
                        "type": "gce_instance",
                        "labels": {
                            "instance_id": f"instance-{generate_random_string(8)}",
                            "zone": "us-central1-a",
                        },
                    },
                    "textPayload": f"Sample {severity} log message {i}",
                    "timestamp": generate_timestamp(
                        datetime.now(timezone.utc)
                        - timedelta(minutes=random.randint(1, 60))
                    ),
                    "severity": severity,
                    "trace": f"projects/test-project/traces/{trace_id or generate_trace_id()}",
                    "labels": {
                        "service": random.choice(
                            ["frontend", "api-gateway", "user-service"]
                        )
                    },
                }
            entries.append(entry)

        return {"entries": entries}
