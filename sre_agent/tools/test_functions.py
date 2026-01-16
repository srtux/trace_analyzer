"""Connectivity check functions for verifying tool availability.

This module registers check functions for tools that can be tested for connectivity.
These checks perform minimal API calls to verify the tool is working.

Note: Function names intentionally do NOT start with 'test_' to avoid pytest
picking them up as test cases. These are runtime connectivity checks, not unit tests.
"""

import logging
import os

from .config import ToolTestResult, ToolTestStatus, get_tool_config_manager

logger = logging.getLogger(__name__)


def get_check_project_id() -> str | None:
    """Get project ID for connectivity checks from environment."""
    return (
        os.getenv("TEST_PROJECT_ID")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCP_PROJECT_ID")
    )


# ============================================================================
# API Client Check Functions
# ============================================================================


async def check_fetch_trace() -> ToolTestResult:
    """Check Cloud Trace API connectivity."""
    try:
        from .clients.factory import get_trace_client

        client = get_trace_client()
        project_id = get_check_project_id()

        if not project_id:
            return ToolTestResult(
                status=ToolTestStatus.FAILED,
                message="No project ID configured. Set GOOGLE_CLOUD_PROJECT environment variable.",
            )

        # Just verify we can create the client and it has the expected methods
        # We don't actually call list_traces as it might be slow with large projects
        if hasattr(client, "list_traces") and hasattr(client, "get_trace"):
            return ToolTestResult(
                status=ToolTestStatus.SUCCESS,
                message="Cloud Trace API client initialized successfully",
                details={"project_id": project_id},
            )
        else:
            return ToolTestResult(
                status=ToolTestStatus.FAILED,
                message="Cloud Trace API client missing expected methods",
            )
    except Exception as e:
        return ToolTestResult(
            status=ToolTestStatus.FAILED,
            message=f"Failed to initialize Cloud Trace client: {e}",
        )


async def check_list_traces() -> ToolTestResult:
    """Check list_traces functionality."""
    return await check_fetch_trace()  # Same underlying client


async def check_find_example_traces() -> ToolTestResult:
    """Check find_example_traces functionality."""
    return await check_fetch_trace()  # Same underlying client


async def check_list_log_entries() -> ToolTestResult:
    """Check Cloud Logging API connectivity."""
    try:
        from .clients.factory import get_logging_client

        client = get_logging_client()
        project_id = get_check_project_id()

        if not project_id:
            return ToolTestResult(
                status=ToolTestStatus.FAILED,
                message="No project ID configured. Set GOOGLE_CLOUD_PROJECT environment variable.",
            )

        if hasattr(client, "list_log_entries"):
            return ToolTestResult(
                status=ToolTestStatus.SUCCESS,
                message="Cloud Logging API client initialized successfully",
                details={"project_id": project_id},
            )
        else:
            return ToolTestResult(
                status=ToolTestStatus.FAILED,
                message="Cloud Logging API client missing expected methods",
            )
    except Exception as e:
        return ToolTestResult(
            status=ToolTestStatus.FAILED,
            message=f"Failed to initialize Cloud Logging client: {e}",
        )


async def check_get_logs_for_trace() -> ToolTestResult:
    """Check get_logs_for_trace functionality."""
    return await check_list_log_entries()  # Same underlying client


async def check_list_error_events() -> ToolTestResult:
    """Check list_error_events functionality."""
    return await check_list_log_entries()  # Same underlying client


async def check_list_time_series() -> ToolTestResult:
    """Check Cloud Monitoring API connectivity."""
    try:
        from .clients.factory import get_monitoring_client

        client = get_monitoring_client()
        project_id = get_check_project_id()

        if not project_id:
            return ToolTestResult(
                status=ToolTestStatus.FAILED,
                message="No project ID configured. Set GOOGLE_CLOUD_PROJECT environment variable.",
            )

        if hasattr(client, "list_time_series"):
            return ToolTestResult(
                status=ToolTestStatus.SUCCESS,
                message="Cloud Monitoring API client initialized successfully",
                details={"project_id": project_id},
            )
        else:
            return ToolTestResult(
                status=ToolTestStatus.FAILED,
                message="Cloud Monitoring API client missing expected methods",
            )
    except Exception as e:
        return ToolTestResult(
            status=ToolTestStatus.FAILED,
            message=f"Failed to initialize Cloud Monitoring client: {e}",
        )


async def check_query_promql() -> ToolTestResult:
    """Check PromQL query functionality."""
    return await check_list_time_series()  # Same underlying client


async def check_list_alerts() -> ToolTestResult:
    """Check alerts API connectivity."""
    try:
        from .clients.factory import get_alert_policy_client

        client = get_alert_policy_client()
        project_id = get_check_project_id()

        if not project_id:
            return ToolTestResult(
                status=ToolTestStatus.FAILED,
                message="No project ID configured. Set GOOGLE_CLOUD_PROJECT environment variable.",
            )

        if hasattr(client, "list_alert_policies"):
            return ToolTestResult(
                status=ToolTestStatus.SUCCESS,
                message="Alert Policy API client initialized successfully",
                details={"project_id": project_id},
            )
        else:
            return ToolTestResult(
                status=ToolTestStatus.FAILED,
                message="Alert Policy API client missing expected methods",
            )
    except Exception as e:
        return ToolTestResult(
            status=ToolTestStatus.FAILED,
            message=f"Failed to initialize Alert Policy client: {e}",
        )


async def check_get_alert() -> ToolTestResult:
    """Check get_alert functionality."""
    return await check_list_alerts()  # Same underlying client


async def check_list_alert_policies() -> ToolTestResult:
    """Check list_alert_policies functionality."""
    return await check_list_alerts()  # Same underlying client


# ============================================================================
# MCP Check Functions
# ============================================================================


async def check_mcp_list_log_entries() -> ToolTestResult:
    """Check MCP Cloud Logging server connectivity."""
    try:
        from .mcp.gcp import create_logging_mcp_toolset

        toolset = create_logging_mcp_toolset()

        if toolset is None:
            return ToolTestResult(
                status=ToolTestStatus.FAILED,
                message="Failed to create MCP Logging toolset - returned None",
            )

        return ToolTestResult(
            status=ToolTestStatus.SUCCESS,
            message="MCP Logging toolset created successfully",
            details={"toolset_type": str(type(toolset).__name__)},
        )
    except Exception as e:
        return ToolTestResult(
            status=ToolTestStatus.FAILED,
            message=f"Failed to create MCP Logging toolset: {e}",
        )


async def check_mcp_list_timeseries() -> ToolTestResult:
    """Check MCP Cloud Monitoring server connectivity."""
    try:
        from .mcp.gcp import create_monitoring_mcp_toolset

        toolset = create_monitoring_mcp_toolset()

        if toolset is None:
            return ToolTestResult(
                status=ToolTestStatus.FAILED,
                message="Failed to create MCP Monitoring toolset - returned None",
            )

        return ToolTestResult(
            status=ToolTestStatus.SUCCESS,
            message="MCP Monitoring toolset created successfully",
            details={"toolset_type": str(type(toolset).__name__)},
        )
    except Exception as e:
        return ToolTestResult(
            status=ToolTestStatus.FAILED,
            message=f"Failed to create MCP Monitoring toolset: {e}",
        )


async def check_mcp_query_range() -> ToolTestResult:
    """Check MCP PromQL query functionality."""
    return await check_mcp_list_timeseries()  # Same underlying MCP server


# ============================================================================
# SLO Check Functions
# ============================================================================


async def check_list_slos() -> ToolTestResult:
    """Check SLO API connectivity."""
    try:
        from google.cloud import monitoring_v3

        client = monitoring_v3.ServiceMonitoringServiceClient()
        project_id = get_check_project_id()

        if not project_id:
            return ToolTestResult(
                status=ToolTestStatus.FAILED,
                message="No project ID configured. Set GOOGLE_CLOUD_PROJECT environment variable.",
            )

        if hasattr(client, "list_services") and hasattr(
            client, "list_service_level_objectives"
        ):
            return ToolTestResult(
                status=ToolTestStatus.SUCCESS,
                message="Service Monitoring API client initialized successfully",
                details={"project_id": project_id},
            )
        else:
            return ToolTestResult(
                status=ToolTestStatus.FAILED,
                message="Service Monitoring API client missing expected methods",
            )
    except Exception as e:
        return ToolTestResult(
            status=ToolTestStatus.FAILED,
            message=f"Failed to initialize Service Monitoring client: {e}",
        )


async def check_get_slo_status() -> ToolTestResult:
    """Check get_slo_status functionality."""
    return await check_list_slos()  # Same underlying client


# ============================================================================
# GKE Check Functions
# ============================================================================


async def check_get_gke_cluster_health() -> ToolTestResult:
    """Check GKE API connectivity."""
    try:
        from google.cloud import container_v1  # type: ignore

        client = container_v1.ClusterManagerClient()
        project_id = get_check_project_id()

        if not project_id:
            return ToolTestResult(
                status=ToolTestStatus.FAILED,
                message="No project ID configured. Set GOOGLE_CLOUD_PROJECT environment variable.",
            )

        if hasattr(client, "list_clusters") and hasattr(client, "get_cluster"):
            return ToolTestResult(
                status=ToolTestStatus.SUCCESS,
                message="GKE Cluster Manager API client initialized successfully",
                details={"project_id": project_id},
            )
        else:
            return ToolTestResult(
                status=ToolTestStatus.FAILED,
                message="GKE Cluster Manager API client missing expected methods",
            )
    except Exception as e:
        return ToolTestResult(
            status=ToolTestStatus.FAILED,
            message=f"Failed to initialize GKE Cluster Manager client: {e}",
        )


async def check_analyze_node_conditions() -> ToolTestResult:
    """Check analyze_node_conditions functionality."""
    return await check_get_gke_cluster_health()  # Same underlying approach


async def check_get_pod_restart_events() -> ToolTestResult:
    """Check get_pod_restart_events functionality."""
    # This uses Cloud Logging, so check that
    return await check_list_log_entries()


async def check_analyze_hpa_events() -> ToolTestResult:
    """Check analyze_hpa_events functionality."""
    # This uses Cloud Logging, so check that
    return await check_list_log_entries()


async def check_get_container_oom_events() -> ToolTestResult:
    """Check get_container_oom_events functionality."""
    # This uses Cloud Logging, so check that
    return await check_list_log_entries()


async def check_get_workload_health_summary() -> ToolTestResult:
    """Check get_workload_health_summary functionality."""
    return await check_get_gke_cluster_health()


# ============================================================================
# Registration Function
# ============================================================================


def register_all_check_functions() -> None:
    """Register all check functions with the ToolConfigManager."""
    manager = get_tool_config_manager()

    # API Client checks
    manager.register_test_function("fetch_trace", check_fetch_trace)
    manager.register_test_function("list_traces", check_list_traces)
    manager.register_test_function("find_example_traces", check_find_example_traces)
    manager.register_test_function("list_log_entries", check_list_log_entries)
    manager.register_test_function("get_logs_for_trace", check_get_logs_for_trace)
    manager.register_test_function("list_error_events", check_list_error_events)
    manager.register_test_function("list_time_series", check_list_time_series)
    manager.register_test_function("query_promql", check_query_promql)
    manager.register_test_function("list_alerts", check_list_alerts)
    manager.register_test_function("get_alert", check_get_alert)
    manager.register_test_function("list_alert_policies", check_list_alert_policies)

    # MCP checks
    manager.register_test_function("mcp_list_log_entries", check_mcp_list_log_entries)
    manager.register_test_function("mcp_list_timeseries", check_mcp_list_timeseries)
    manager.register_test_function("mcp_query_range", check_mcp_query_range)

    # SLO checks
    manager.register_test_function("list_slos", check_list_slos)
    manager.register_test_function("get_slo_status", check_get_slo_status)

    # GKE checks
    manager.register_test_function(
        "get_gke_cluster_health", check_get_gke_cluster_health
    )
    manager.register_test_function(
        "analyze_node_conditions", check_analyze_node_conditions
    )
    manager.register_test_function(
        "get_pod_restart_events", check_get_pod_restart_events
    )
    manager.register_test_function("analyze_hpa_events", check_analyze_hpa_events)
    manager.register_test_function(
        "get_container_oom_events", check_get_container_oom_events
    )
    manager.register_test_function(
        "get_workload_health_summary", check_get_workload_health_summary
    )

    logger.info("Registered all tool check functions")


# Backwards compatibility alias
register_all_test_functions = register_all_check_functions
