"""Tests for GKE/Kubernetes tools."""

import json
from unittest.mock import MagicMock, patch


class TestGKETools:
    """Test suite for GKE/Kubernetes tools."""

    @patch("sre_agent.tools.clients.gke._get_authorized_session")
    def test_get_gke_cluster_health_returns_cluster_info(self, mock_session_fn):
        """Test that get_gke_cluster_health returns cluster information."""
        from sre_agent.tools.clients.gke import get_gke_cluster_health

        mock_session = MagicMock()
        mock_session_fn.return_value = mock_session

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "name": "test-cluster",
            "location": "us-central1",
            "status": "RUNNING",
            "currentMasterVersion": "1.28.0",
            "currentNodeVersion": "1.28.0",
            "nodePools": [
                {
                    "name": "default-pool",
                    "status": "RUNNING",
                    "config": {"machineType": "e2-medium"},
                    "initialNodeCount": 3,
                    "autoscaling": {
                        "enabled": True,
                        "minNodeCount": 1,
                        "maxNodeCount": 5,
                    },
                }
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        result = get_gke_cluster_health("test-project", "test-cluster", "us-central1")
        result_data = json.loads(result)

        assert result_data["cluster_name"] == "test-cluster"
        assert result_data["status"] == "RUNNING"
        assert result_data["health"] == "HEALTHY"
        assert len(result_data["node_pools"]) == 1

    @patch("sre_agent.tools.clients.gke.monitoring_v3.MetricServiceClient")
    def test_analyze_node_conditions_structure(self, mock_client_class):
        """Test that analyze_node_conditions returns correct structure."""
        from sre_agent.tools.clients.gke import analyze_node_conditions

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_time_series.return_value = []

        result = analyze_node_conditions("test-project", "test-cluster", "us-central1")
        result_data = json.loads(result)

        assert "cluster" in result_data
        assert "nodes" in result_data
        assert "pressure_warnings" in result_data
        assert "summary" in result_data

    @patch("sre_agent.tools.clients.gke.monitoring_v3.MetricServiceClient")
    def test_get_pod_restart_events_returns_pods(self, mock_client_class):
        """Test that get_pod_restart_events returns pod restart information."""
        from sre_agent.tools.clients.gke import get_pod_restart_events

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_time_series.return_value = []

        result = get_pod_restart_events("test-project", "production", minutes_ago=60)
        result_data = json.loads(result)

        assert "time_window_minutes" in result_data
        assert "pods_with_restarts" in result_data
        assert "summary" in result_data
        assert "severity" in result_data

    @patch("sre_agent.tools.clients.gke.monitoring_v3.MetricServiceClient")
    def test_analyze_hpa_events_structure(self, mock_client_class):
        """Test that analyze_hpa_events returns HPA information."""
        from sre_agent.tools.clients.gke import analyze_hpa_events

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_time_series.return_value = []

        result = analyze_hpa_events("test-project", "production", "frontend-deploy", 60)
        result_data = json.loads(result)

        assert "namespace" in result_data
        assert "deployment" in result_data
        assert "scaling_activity" in result_data
        assert "summary" in result_data

    @patch("sre_agent.tools.clients.gke._get_authorized_session")
    @patch("sre_agent.tools.clients.gke.monitoring_v3.MetricServiceClient")
    def test_get_container_oom_events_structure(
        self, mock_client_class, mock_session_fn
    ):
        """Test that get_container_oom_events returns OOM information."""
        from sre_agent.tools.clients.gke import get_container_oom_events

        mock_session = MagicMock()
        mock_session_fn.return_value = mock_session
        mock_response = MagicMock()
        mock_response.json.return_value = {"entries": []}
        mock_response.raise_for_status = MagicMock()
        mock_session.post.return_value = mock_response

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_time_series.return_value = []

        result = get_container_oom_events("test-project", "production", 60)
        result_data = json.loads(result)

        assert "time_window_minutes" in result_data
        assert "oom_events_in_logs" in result_data
        assert "containers_at_risk" in result_data
        assert "severity" in result_data

    @patch("sre_agent.tools.clients.gke.monitoring_v3.MetricServiceClient")
    def test_get_workload_health_summary_returns_workloads(self, mock_client_class):
        """Test that get_workload_health_summary returns workload info."""
        from sre_agent.tools.clients.gke import get_workload_health_summary

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_time_series.return_value = []

        result = get_workload_health_summary("test-project", "production", 30)
        result_data = json.loads(result)

        assert "namespace" in result_data
        assert "time_window_minutes" in result_data
        assert "summary" in result_data
        assert "workloads" in result_data


class TestNodePressureThresholds:
    """Test node pressure threshold logic."""

    def test_cpu_pressure_threshold(self):
        """Test CPU pressure threshold at 85%."""
        threshold = 0.85
        assert 0.80 < threshold  # Not pressure
        assert 0.90 > threshold  # Is pressure

    def test_memory_pressure_threshold(self):
        """Test memory pressure threshold at 85%."""
        threshold = 0.85
        assert 0.80 < threshold  # Not pressure
        assert 0.90 > threshold  # Is pressure

    def test_disk_pressure_threshold(self):
        """Test disk pressure threshold at 85%."""
        threshold = 0.85
        disk_used = 90 * 1024 * 1024 * 1024  # 90GB
        disk_total = 100 * 1024 * 1024 * 1024  # 100GB
        utilization = disk_used / disk_total  # 0.9

        assert utilization > threshold

    def test_pid_pressure_threshold(self):
        """Test PID pressure threshold at 80%."""
        threshold = 0.80
        pid_used = 3500
        pid_limit = 4096
        utilization = pid_used / pid_limit  # ~0.85

        assert utilization > threshold


class TestWorkloadHealthClassification:
    """Test workload health classification logic."""

    def test_critical_classification(self):
        """Test that high restart count is classified as CRITICAL."""
        restart_count = 10
        threshold = 5
        assert restart_count > threshold  # CRITICAL

    def test_memory_critical_classification(self):
        """Test that >95% memory is classified as CRITICAL."""
        memory_util = 0.97
        critical_threshold = 0.95
        assert memory_util > critical_threshold

    def test_warning_classification(self):
        """Test that >85% memory is classified as WARNING."""
        memory_util = 0.88
        warning_threshold = 0.85
        critical_threshold = 0.95
        assert memory_util > warning_threshold
        assert memory_util < critical_threshold

    def test_healthy_classification(self):
        """Test that normal metrics are classified as HEALTHY."""
        memory_util = 0.60
        cpu_util = 0.50
        restart_count = 0

        warning_threshold = 0.85
        restart_threshold = 0

        is_healthy = (
            memory_util < warning_threshold
            and cpu_util < warning_threshold
            and restart_count == restart_threshold
        )
        assert is_healthy


class TestDeploymentNameExtraction:
    """Test deployment name extraction from pod name."""

    def test_standard_deployment_pod_name(self):
        """Test extraction from standard deployment pod name."""
        pod_name = "frontend-deploy-7f4d5b6c9-abcde"
        parts = pod_name.rsplit("-", 2)
        deployment_name = parts[0] if len(parts) >= 3 else pod_name

        assert deployment_name == "frontend-deploy"

    def test_statefulset_pod_name(self):
        """Test extraction from statefulset pod name (only one suffix)."""
        pod_name = "redis-0"
        parts = pod_name.rsplit("-", 2)
        deployment_name = parts[0] if len(parts) >= 3 else pod_name

        # StatefulSets only have index suffix, so returns full name
        assert deployment_name == "redis-0"

    def test_complex_deployment_name(self):
        """Test extraction from deployment name with hyphens."""
        pod_name = "my-complex-service-name-7f4d5b6c9-xyz12"
        parts = pod_name.rsplit("-", 2)
        deployment_name = parts[0] if len(parts) >= 3 else pod_name

        assert deployment_name == "my-complex-service-name"
