"""Trace filter utilities for building Cloud Trace query strings."""

import numpy as np

from ..common import adk_tool


class TraceSelector:
    """
    Provides different strategies for selecting traces for analysis.
    """

    def from_error_reports(self, project_id: str) -> list[str]:
        """
        Selects traces associated with recent error reports.
        (Placeholder - requires Error Reporting API client)
        """
        print("Warning: Trace selection from error reports is not yet implemented.")
        return []

    def from_monitoring_alerts(self, project_id: str) -> list[str]:
        """
        Selects traces associated with active monitoring alerts.
        (Placeholder - requires Monitoring API client)
        """
        print("Warning: Trace selection from monitoring alerts is not yet implemented.")
        return []

    def from_statistical_outliers(self, traces: list[dict]) -> list[str]:
        """
        Selects traces that are statistical outliers based on latency.
        An outlier is defined as a trace with a latency greater than 2 standard
        deviations from the mean.
        """
        if not traces:
            return []

        latencies = [trace.get("latency", 0) for trace in traces]
        mean_latency = np.mean(latencies)
        std_dev_latency = np.std(latencies)
        threshold = mean_latency + 2 * std_dev_latency

        outlier_trace_ids = [
            trace["traceId"] for trace in traces if trace.get("latency", 0) > threshold
        ]
        return outlier_trace_ids

    def from_manual_override(self, trace_ids: list[str]) -> list[str]:
        """
        Allows manually specifying a list of trace IDs.
        """
        return trace_ids


@adk_tool
def select_traces_from_error_reports(project_id: str) -> list[str]:
    """
    Selects traces to analyze based on recent error reports.

    Args:
        project_id: The Google Cloud project ID.

    Returns:
        A list of trace IDs.
    """
    selector = TraceSelector()
    return selector.from_error_reports(project_id)


@adk_tool
def select_traces_from_monitoring_alerts(project_id: str) -> list[str]:
    """
    Selects traces to analyze based on active monitoring alerts.

    Args:
        project_id: The Google Cloud project ID.

    Returns:
        A list of trace IDs.
    """
    selector = TraceSelector()
    return selector.from_monitoring_alerts(project_id)


@adk_tool
def select_traces_from_statistical_outliers(traces: list[dict]) -> list[str]:
    """
    Selects outlier traces from a given list of traces based on latency.

    Args:
        traces: A list of trace dictionaries, each with a 'latency' and 'traceId'.

    Returns:
        A list of outlier trace IDs.
    """
    selector = TraceSelector()
    return selector.from_statistical_outliers(traces)


@adk_tool
def select_traces_manually(trace_ids: list[str]) -> list[str]:
    """
    Allows a user to manually provide a list of trace IDs for analysis.

    Args:
        trace_ids: A list of trace IDs.

    Returns:
        The same list of trace IDs.
    """
    selector = TraceSelector()
    return selector.from_manual_override(trace_ids)


class TraceQueryBuilder:
    """
    Builder for Google Cloud Trace filter strings.

    See: https://docs.cloud.google.com/trace/docs/trace-filters
    """

    def __init__(self):
        self._terms: list[str] = []

    def _add_term(self, term: str, root_only: bool = False):
        if root_only:
            self._terms.append(f"^{term}")
        else:
            self._terms.append(term)

    def span_name(
        self, name: str, match_exact: bool = False, root_only: bool = False
    ) -> "TraceQueryBuilder":
        """
        Filter by span name.

        Args:
            name: The span name to filter for.
            match_exact: If True, uses `+span:name`.
            root_only: If True, restricts to root span.
        """
        prefix = "+" if match_exact else ""

        if root_only:
            term = f"root:{name}"
        else:
            term = f"span:{name}"

        self._terms.append(f"{prefix}{term}")
        return self

    def latency(
        self, min_latency_ms: int | None = None, max_latency_ms: int | None = None
    ) -> "TraceQueryBuilder":
        """
        Filter by latency.

        Args:
            min_latency_ms: Minimum latency in milliseconds.
            max_latency_ms: Maximum latency (not directly supported).
        """
        if min_latency_ms is not None:
            self._terms.append(f"latency:{min_latency_ms}ms")

        return self

    def attribute(
        self, key: str, value: str, match_exact: bool = False, root_only: bool = False
    ) -> "TraceQueryBuilder":
        """
        Filter by attribute (label) key/value.

        Args:
            key: Attribute key (e.g. '/http/status_code').
            value: Attribute value.
            match_exact: If True, requires exact match.
            root_only: If True, restricts to root span.
        """
        term = f"{key}:{value}"

        prefix = ""
        if match_exact:
            prefix += "+"
        if root_only:
            prefix += "^"

        self._terms.append(f"{prefix}{term}")
        return self

    def service_name(self, name: str, match_exact: bool = False) -> "TraceQueryBuilder":
        """Helper for service name filtering."""
        return self.attribute("service.name", name, match_exact=match_exact)

    def status(self, code: int, root_only: bool = False) -> "TraceQueryBuilder":
        """Filter by HTTP status code."""
        return self.attribute("/http/status_code", str(code), root_only=root_only)

    def method(self, method: str, root_only: bool = False) -> "TraceQueryBuilder":
        """Filter by HTTP method."""
        term = f"method:{method}"
        if root_only:
            term = f"^{term}"
        self._terms.append(term)
        return self

    def url(self, url: str, root_only: bool = False) -> "TraceQueryBuilder":
        """Filter by URL."""
        term = f"url:{url}"
        if root_only:
            term = f"^{term}"
        self._terms.append(term)
        return self

    def build(self) -> str:
        """Returns the constructed filter string."""
        return " ".join(self._terms)

    def clear(self):
        self._terms = []


def build_trace_filter(
    min_latency_ms: int | None = None,
    max_latency_ms: int | None = None,
    error_only: bool = False,
    service_name: str | None = None,
    http_status: int | None = None,
    attributes: dict[str, str] | None = None,
    custom_filter: str | None = None,
) -> str:
    """
    Build Cloud Trace filter string using TraceQueryBuilder.

    This is a convenience function that simplifies creating trace filters
    for common use cases.

    Args:
        min_latency_ms: Minimum latency in milliseconds.
        max_latency_ms: Maximum latency in milliseconds (not widely supported).
        error_only: If True, filters for traces with errors.
        service_name: Filter by service name.
        http_status: Filter by HTTP status code.
        attributes: Dictionary of attribute key-value pairs to filter by.
        custom_filter: If provided, returns this instead of building a new filter.

    Returns:
        Cloud Trace filter string.

    Example:
        >>> build_trace_filter(min_latency_ms=500, error_only=True)
        'latency:500ms error:true'
    """
    if custom_filter:
        return custom_filter

    builder = TraceQueryBuilder()

    if min_latency_ms or max_latency_ms:
        builder.latency(min_latency_ms=min_latency_ms, max_latency_ms=max_latency_ms)

    if error_only:
        builder.attribute("error", "true")

    if service_name:
        builder.service_name(service_name)

    if http_status:
        builder.status(http_status)

    if attributes:
        for k, v in attributes.items():
            builder.attribute(k, v)

    return builder.build()
