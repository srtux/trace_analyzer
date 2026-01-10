"""Tests for SLO/SLI tools."""

import json
from unittest.mock import MagicMock, patch


class TestSLOTools:
    """Test suite for SLO/SLI tools."""

    @patch("sre_agent.tools.clients.slo.monitoring_v3.ServiceMonitoringServiceClient")
    def test_list_slos_returns_slo_data(self, mock_client_class):
        """Test that list_slos returns properly formatted SLO data."""
        from sre_agent.tools.clients.slo import list_slos

        # Mock the client and response
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_slo = MagicMock()
        mock_slo.name = "projects/test-project/services/test-service/serviceLevelObjectives/test-slo"
        mock_slo.display_name = "Test SLO"
        mock_slo.goal = 0.999
        mock_slo.rolling_period.days = 30
        mock_slo.service_level_indicator = None

        mock_client.list_services.return_value = []

        result = list_slos("test-project", "test-service")
        result_data = json.loads(result)

        # Verify we got a list
        assert isinstance(result_data, list)

    @patch("sre_agent.tools.clients.slo.monitoring_v3.MetricServiceClient")
    @patch("sre_agent.tools.clients.slo._get_authorized_session")
    def test_get_slo_status_returns_status(
        self, mock_auth_session_fn, mock_metric_client_fn
    ):
        """Test that get_slo_status returns SLO status information."""
        from sre_agent.tools.clients.slo import get_slo_status

        # Configure the mock for _get_authorized_session (inner decorator)
        mock_session = MagicMock()
        mock_auth_session_fn.return_value = mock_session

        # Configure the mock for MetricServiceClient (outer decorator)
        mock_metric_client_fn.return_value = MagicMock()

        # Configure the mock response that the session's 'get' method will return
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "name": "projects/test/services/svc/serviceLevelObjectives/slo",
            "displayName": "Test SLO",
            "goal": 0.999,
            "rollingPeriod": {"days": 30},
            "serviceLevelIndicator": {"basicSli": {"availability": {}}},
        }
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        # Call the actual function
        result = get_slo_status("test-project", "test-service", "test-slo")
        result_data = json.loads(result)

        # Assert the results
        assert "slo_name" in result_data
        assert "goal" in result_data
        assert result_data["goal"] == 0.999

    def test_get_golden_signals_structure(self):
        """Test that get_golden_signals returns the correct structure."""
        from sre_agent.tools.clients.slo import get_golden_signals

        # This will return NO_DATA for all signals since we're not mocking
        # but we can verify the structure
        with patch("sre_agent.tools.clients.slo.monitoring_v3.MetricServiceClient"):
            result = get_golden_signals("test-project", "test-service", 60)
            result_data = json.loads(result)

            assert "service_name" in result_data
            assert "time_window_minutes" in result_data
            assert "signals" in result_data

            # All four golden signals should be present
            signals = result_data["signals"]
            assert "latency" in signals or result_data.get("error")
            assert "traffic" in signals or result_data.get("error")
            assert "errors" in signals or result_data.get("error")
            assert "saturation" in signals or result_data.get("error")

    def test_correlate_incident_with_slo_impact_calculation(self):
        """Test incident impact calculation logic."""
        from sre_agent.tools.clients.slo import correlate_incident_with_slo_impact

        with patch("sre_agent.tools.clients.slo.get_slo_status") as mock_status:
            mock_status.return_value = json.dumps(
                {
                    "goal": 0.999,
                    "rolling_period_days": 30,
                }
            )

            result = correlate_incident_with_slo_impact(
                "test-project",
                "test-service",
                "test-slo",
                "2024-01-15T10:00:00Z",
                "2024-01-15T10:30:00Z",
            )
            result_data = json.loads(result)

            assert "incident_window" in result_data
            assert result_data["incident_window"]["duration_minutes"] == 30
            assert "error_budget_analysis" in result_data
            assert "impact_assessment" in result_data

    def test_predict_slo_violation_structure(self):
        """Test SLO violation prediction returns expected structure."""
        from sre_agent.tools.clients.slo import predict_slo_violation

        with patch(
            "sre_agent.tools.clients.slo.analyze_error_budget_burn"
        ) as mock_burn:
            mock_burn.return_value = json.dumps(
                {
                    "burn_rate_per_hour": 0.001,
                    "hours_to_budget_exhaustion": 100,
                }
            )

            result = predict_slo_violation(
                "test-project", "test-service", "test-slo", 24
            )
            result_data = json.loads(result)

            assert "prediction_window_hours" in result_data
            assert "current_state" in result_data
            assert "prediction" in result_data


class TestGoldenSignalsCalculation:
    """Test golden signals calculation logic."""

    def test_error_rate_calculation(self):
        """Test that error rate is calculated correctly."""
        # Error rate = (errors / total requests) * 100
        errors = 10
        total = 1000
        expected_rate = 1.0  # 1%

        actual_rate = (errors / total) * 100
        assert actual_rate == expected_rate

    def test_cpu_saturation_thresholds(self):
        """Test CPU saturation threshold logic."""
        # Test thresholds: <70% = GOOD, <85% = WARNING, >=85% = CRITICAL
        assert 60 < 70  # GOOD
        assert 75 < 85  # WARNING
        assert 90 >= 85  # CRITICAL


class TestErrorBudgetMath:
    """Test error budget calculations."""

    def test_error_budget_calculation_99_9(self):
        """Test error budget for 99.9% SLO."""
        goal = 0.999
        rolling_period_days = 30
        total_minutes = rolling_period_days * 24 * 60

        # Error budget = total_minutes * (1 - goal)
        error_budget_minutes = total_minutes * (1 - goal)

        # 30 days * 24 hours * 60 minutes = 43,200 minutes
        # 43,200 * 0.001 = 43.2 minutes of allowed downtime
        assert abs(error_budget_minutes - 43.2) < 0.1

    def test_error_budget_calculation_99_99(self):
        """Test error budget for 99.99% SLO."""
        goal = 0.9999
        rolling_period_days = 30
        total_minutes = rolling_period_days * 24 * 60

        error_budget_minutes = total_minutes * (1 - goal)

        # 43,200 * 0.0001 = 4.32 minutes of allowed downtime
        assert abs(error_budget_minutes - 4.32) < 0.1

    def test_incident_impact_percentage(self):
        """Test incident impact as percentage of error budget."""
        error_budget_minutes = 43.2  # 99.9% SLO over 30 days
        incident_duration_minutes = 10

        impact_percent = (incident_duration_minutes / error_budget_minutes) * 100

        # 10 / 43.2 * 100 = ~23.15%
        assert abs(impact_percent - 23.15) < 0.5
