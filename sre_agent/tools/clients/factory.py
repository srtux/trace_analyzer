"""Lazy initialization for GCP service clients to optimize resource usage."""

import threading
from typing import Any, TypeVar, cast

from google.cloud import monitoring_v3, trace_v1
from google.cloud.logging_v2.services.logging_service_v2 import LoggingServiceV2Client

from ...auth import get_current_credentials_or_none

T = TypeVar("T")

_clients: dict[str, Any] = {}
_lock = threading.Lock()


def _get_client(name: str, client_class: type[T]) -> T:
    """Helper for thread-safe lazy initialization of clients.

    Args:
        name: Unique name/key for the client instance.
        client_class: The client class to instantiate.

    Returns:
        The initialized client instance.
    """
    if name not in _clients:
        with _lock:
            if name not in _clients:
                _clients[name] = client_class()

    # Check for user-specific credentials override
    user_creds = get_current_credentials_or_none()
    if user_creds:
        # Create a new client with these credentials
        # We don't cache these in the global cache to avoid mixing user sessions.
        # In a high-throughput scenario, we might want a per-user cache.
        return client_class(credentials=user_creds)  # type: ignore[call-arg]

    return cast(T, _clients[name])


def get_trace_client() -> trace_v1.TraceServiceClient:
    """Returns a singleton Cloud Trace client."""
    return _get_client("trace", trace_v1.TraceServiceClient)


def get_logging_client() -> LoggingServiceV2Client:
    """Returns a singleton Cloud Logging client."""
    return _get_client("logging", LoggingServiceV2Client)


def get_monitoring_client() -> monitoring_v3.MetricServiceClient:
    """Returns a singleton Cloud Monitoring client."""
    return _get_client("monitoring", monitoring_v3.MetricServiceClient)


def get_alert_policy_client() -> monitoring_v3.AlertPolicyServiceClient:
    """Returns a singleton Cloud Monitoring Alert Policy client."""
    return _get_client("alert_policies", monitoring_v3.AlertPolicyServiceClient)
