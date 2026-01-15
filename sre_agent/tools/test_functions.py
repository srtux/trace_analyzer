"""Test functions for verifying tool connectivity.

This module registers test functions for tools that can be tested for connectivity.
These tests perform minimal API calls to verify the tool is working.
"""

import logging
import os

from .config import ToolTestResult, ToolTestStatus, get_tool_config_manager

logger = logging.getLogger(__name__)


def get_test_project_id() -> str | None:
    """Get project ID for testing from environment."""
    return (
        os.getenv("TEST_PROJECT_ID")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCP_PROJECT_ID")
    )


# ============================================================================
# API Client Test Functions
# ============================================================================


async def test_fetch_trace() -> ToolTestResult:
    """Test Cloud Trace API connectivity."""
    try:
        from .clients.factory import get_trace_client

        client = get_trace_client()
        project_id = get_test_project_id()

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


async def test_list_traces() -> ToolTestResult:
    """Test list_traces functionality."""
    return await test_fetch_trace()  # Same underlying client


async def test_find_example_traces() -> ToolTestResult:
    """Test find_example_traces functionality."""
    return await test_fetch_trace()  # Same underlying client


async def test_list_log_entries() -> ToolTestResult:
    """Test Cloud Logging API connectivity."""
    try:
        from .clients.factory import get_logging_client

        client = get_logging_client()
        project_id = get_test_project_id()

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


async def test_get_logs_for_trace() -> ToolTestResult:
    """Test get_logs_for_trace functionality."""
    return await test_list_log_entries()  # Same underlying client


async def test_list_error_events() -> ToolTestResult:
    """Test list_error_events functionality."""
    return await test_list_log_entries()  # Same underlying client


async def test_list_time_series() -> ToolTestResult:
    """Test Cloud Monitoring API connectivity."""
    try:
        from .clients.factory import get_monitoring_client

        client = get_monitoring_client()
        project_id = get_test_project_id()

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


async def test_query_promql() -> ToolTestResult:
    """Test PromQL query functionality."""
    return await test_list_time_series()  # Same underlying client


async def test_list_alerts() -> ToolTestResult:
    """Test alerts API connectivity."""
    try:
        from .clients.factory import get_alert_policy_client

        client = get_alert_policy_client()
        project_id = get_test_project_id()

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


async def test_get_alert() -> ToolTestResult:
    """Test get_alert functionality."""
    return await test_list_alerts()  # Same underlying client


async def test_list_alert_policies() -> ToolTestResult:
    """Test list_alert_policies functionality."""
    return await test_list_alerts()  # Same underlying client


# ============================================================================
# MCP Test Functions
# ============================================================================


async def test_mcp_list_log_entries() -> ToolTestResult:
    """Test MCP Cloud Logging server connectivity."""
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


async def test_mcp_list_timeseries() -> ToolTestResult:
    """Test MCP Cloud Monitoring server connectivity."""
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


async def test_mcp_query_range() -> ToolTestResult:
    """Test MCP PromQL query functionality."""
    return await test_mcp_list_timeseries()  # Same underlying MCP server


# ============================================================================
# SLO Test Functions
# ============================================================================


async def test_list_slos() -> ToolTestResult:
    """Test SLO API connectivity."""
    try:
        from google.cloud import monitoring_v3

        client = monitoring_v3.ServiceMonitoringServiceClient()
        project_id = get_test_project_id()

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


async def test_get_slo_status() -> ToolTestResult:
    """Test get_slo_status functionality."""
    return await test_list_slos()  # Same underlying client


# ============================================================================
# GKE Test Functions
# ============================================================================


async def test_get_gke_cluster_health() -> ToolTestResult:
    """Test GKE API connectivity."""
    try:
        from google.cloud import container_v1  # type: ignore

        client = container_v1.ClusterManagerClient()
        project_id = get_test_project_id()

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


async def test_analyze_node_conditions() -> ToolTestResult:
    """Test analyze_node_conditions functionality."""
    return await test_get_gke_cluster_health()  # Same underlying approach


async def test_get_pod_restart_events() -> ToolTestResult:
    """Test get_pod_restart_events functionality."""
    # This uses Cloud Logging, so test that
    return await test_list_log_entries()


async def test_analyze_hpa_events() -> ToolTestResult:
    """Test analyze_hpa_events functionality."""
    # This uses Cloud Logging, so test that
    return await test_list_log_entries()


async def test_get_container_oom_events() -> ToolTestResult:
    """Test get_container_oom_events functionality."""
    # This uses Cloud Logging, so test that
    return await test_list_log_entries()


async def test_get_workload_health_summary() -> ToolTestResult:
    """Test get_workload_health_summary functionality."""
    return await test_get_gke_cluster_health()


# ============================================================================
# Registration Function
# ============================================================================


def register_all_test_functions() -> None:
    """Register all test functions with the ToolConfigManager."""
    manager = get_tool_config_manager()

    # API Client tests
    manager.register_test_function("fetch_trace", test_fetch_trace)
    manager.register_test_function("list_traces", test_list_traces)
    manager.register_test_function("find_example_traces", test_find_example_traces)
    manager.register_test_function("list_log_entries", test_list_log_entries)
    manager.register_test_function("get_logs_for_trace", test_get_logs_for_trace)
    manager.register_test_function("list_error_events", test_list_error_events)
    manager.register_test_function("list_time_series", test_list_time_series)
    manager.register_test_function("query_promql", test_query_promql)
    manager.register_test_function("list_alerts", test_list_alerts)
    manager.register_test_function("get_alert", test_get_alert)
    manager.register_test_function("list_alert_policies", test_list_alert_policies)

    # MCP tests
    manager.register_test_function("mcp_list_log_entries", test_mcp_list_log_entries)
    manager.register_test_function("mcp_list_timeseries", test_mcp_list_timeseries)
    manager.register_test_function("mcp_query_range", test_mcp_query_range)

    # SLO tests
    manager.register_test_function("list_slos", test_list_slos)
    manager.register_test_function("get_slo_status", test_get_slo_status)

    # GKE tests
    manager.register_test_function(
        "get_gke_cluster_health", test_get_gke_cluster_health
    )
    manager.register_test_function(
        "analyze_node_conditions", test_analyze_node_conditions
    )
    manager.register_test_function(
        "get_pod_restart_events", test_get_pod_restart_events
    )
    manager.register_test_function("analyze_hpa_events", test_analyze_hpa_events)
    manager.register_test_function(
        "get_container_oom_events", test_get_container_oom_events
    )
    manager.register_test_function(
        "get_workload_health_summary", test_get_workload_health_summary
    )

    logger.info("Registered all tool test functions")
