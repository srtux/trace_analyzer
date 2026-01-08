
import os
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio


# Mock google.adk components
mock_adk = MagicMock()
sys.modules["google.adk"] = mock_adk
sys.modules["google.adk.agents"] = mock_adk
sys.modules["google.adk.tools"] = mock_adk
sys.modules["google.adk.tools.api_registry"] = MagicMock() # Mock the registry module
sys.modules["google.adk.tools.base_toolset"] = MagicMock()

sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.trace_v1"] = MagicMock()
sys.modules["opentelemetry"] = MagicMock()
sys.modules["opentelemetry.trace"] = MagicMock()
sys.modules["opentelemetry.metrics"] = MagicMock()
sys.modules["google.cloud.logging_v2"] = MagicMock()
sys.modules["google.cloud.logging_v2.services"] = MagicMock()
sys.modules["google.cloud.logging_v2.services.logging_service_v2"] = MagicMock()
sys.modules["google.cloud.errorreporting_v1beta1"] = MagicMock()
sys.modules["google.cloud.monitoring_v3"] = MagicMock()
# Mock google.auth return value explicitly on the mock object
mock_auth = MagicMock()
sys.modules["google.auth"] = mock_auth
# Use side_effect or return_value for default
# Start of mock setup
mock_auth.default.return_value = (MagicMock(), "mock-project-id")
import google  # noqa: E402

google.auth = mock_auth

class TestMCPIntegration(unittest.TestCase):

    def test_create_bigquery_mcp_toolset_simple(self):
        """Test that create_bigquery_mcp_toolset creates toolset following blog post pattern."""
        # We'll use the mock we injected into sys.modules
        mock_registry_module = sys.modules["google.adk.tools.api_registry"]
        mock_registry_cls = mock_registry_module.ApiRegistry

        # Reset mocks
        mock_registry_cls.reset_mock()

        # Reload agent to ensure it picks up the mocks and runs clean
        if "trace_analyzer.agent" in sys.modules:
            del sys.modules["trace_analyzer.agent"]
        from trace_analyzer.agent import create_bigquery_mcp_toolset

        # Setup registry mock instance interactions
        mock_registry_instance = mock_registry_cls.return_value
        mock_toolset = MagicMock()
        mock_registry_instance.get_toolset.return_value = mock_toolset

        # Test: create toolset (synchronous, no await)
        toolset = create_bigquery_mcp_toolset("test-project")

        # Verify toolset was returned (not tools)
        self.assertIsNotNone(toolset)
        self.assertEqual(toolset, mock_toolset)

        # Verify get_toolset was called
        mock_registry_instance.get_toolset.assert_called_once()

        # Verify get_tools() was NOT called (ADK framework will call it)
        self.assertFalse(hasattr(mock_toolset.get_tools, 'call_count') or mock_toolset.get_tools.call_count == 0)

    def test_create_bigquery_mcp_toolset_no_project(self):
        """Test that create_bigquery_mcp_toolset handles missing project ID gracefully."""
        # Reload agent
        if "trace_analyzer.agent" in sys.modules:
            del sys.modules["trace_analyzer.agent"]
        from trace_analyzer.agent import create_bigquery_mcp_toolset

        # Test with None project_id
        toolset = create_bigquery_mcp_toolset(None)
        self.assertIsNone(toolset)

        # Test with empty string
        toolset = create_bigquery_mcp_toolset("")
        self.assertIsNone(toolset)

    def test_create_bigquery_mcp_toolset_error_handling(self):
        """Test that create_bigquery_mcp_toolset handles errors gracefully."""
        mock_registry_module = sys.modules["google.adk.tools.api_registry"]
        mock_registry_cls = mock_registry_module.ApiRegistry

        # Reload agent
        if "trace_analyzer.agent" in sys.modules:
            del sys.modules["trace_analyzer.agent"]
        from trace_analyzer.agent import create_bigquery_mcp_toolset

        # Setup mock to raise error during get_toolset
        mock_registry_instance = mock_registry_cls.return_value
        mock_registry_instance.get_toolset.side_effect = Exception("Connection error")

        # Test: should return None on error (not raise)
        toolset = create_bigquery_mcp_toolset("test-project")
        self.assertIsNone(toolset)


if __name__ == "__main__":
    unittest.main()
