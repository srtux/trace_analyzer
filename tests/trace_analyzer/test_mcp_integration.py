import os
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from types import ModuleType


# Create mock google module hierarchy before any imports
mock_google = ModuleType("google")
mock_auth = MagicMock()
mock_auth.default.return_value = (MagicMock(), "mock-project-id")
mock_google.auth = mock_auth

# Mock google.adk components
mock_adk = MagicMock()

# Register all mocks in sys.modules
sys.modules["google"] = mock_google
sys.modules["google.auth"] = mock_auth
sys.modules["google.adk"] = mock_adk
sys.modules["google.adk.agents"] = mock_adk
sys.modules["google.adk.tools"] = mock_adk
sys.modules["google.adk.tools.api_registry"] = MagicMock()  # Mock the registry module
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

# Mock additional dependencies
sys.modules["numpy"] = MagicMock()
sys.modules["scipy"] = MagicMock()
sys.modules["scipy.stats"] = MagicMock()

class TestMCPIntegration(unittest.TestCase):

    def test_module_level_toolset_singleton(self):
        """Test that the module-level MCP toolset singleton is created correctly."""
        # Setup registry mock
        mock_registry_module = sys.modules["google.adk.tools.api_registry"]
        mock_registry_cls = mock_registry_module.ApiRegistry
        mock_registry_cls.reset_mock()

        mock_toolset = MagicMock()
        mock_registry_instance = mock_registry_cls.return_value
        mock_registry_instance.get_toolset.return_value = mock_toolset

        # Reload agent to trigger module-level toolset creation
        if "trace_analyzer.agent" in sys.modules:
            del sys.modules["trace_analyzer.agent"]
        from trace_analyzer.agent import get_bigquery_mcp_toolset, _bigquery_mcp_toolset

        # Verify get_bigquery_mcp_toolset returns the module-level singleton
        result = get_bigquery_mcp_toolset()
        self.assertEqual(result, _bigquery_mcp_toolset)

    def test_get_bigquery_mcp_toolset_returns_singleton(self):
        """Test that get_bigquery_mcp_toolset() always returns the same instance."""
        # Reload agent
        if "trace_analyzer.agent" in sys.modules:
            del sys.modules["trace_analyzer.agent"]
        from trace_analyzer.agent import get_bigquery_mcp_toolset

        # Call multiple times - should always return the same instance
        result1 = get_bigquery_mcp_toolset()
        result2 = get_bigquery_mcp_toolset()
        result3 = get_bigquery_mcp_toolset()

        self.assertIs(result1, result2)
        self.assertIs(result2, result3)

    def test_create_bigquery_mcp_toolset_deprecated_returns_singleton(self):
        """Test that deprecated create_bigquery_mcp_toolset returns the singleton."""
        # Setup registry mock
        mock_registry_module = sys.modules["google.adk.tools.api_registry"]
        mock_registry_cls = mock_registry_module.ApiRegistry
        mock_registry_cls.reset_mock()

        mock_toolset = MagicMock()
        mock_registry_instance = mock_registry_cls.return_value
        mock_registry_instance.get_toolset.return_value = mock_toolset

        # Reload agent
        if "trace_analyzer.agent" in sys.modules:
            del sys.modules["trace_analyzer.agent"]
        from trace_analyzer.agent import create_bigquery_mcp_toolset, get_bigquery_mcp_toolset

        # Test: deprecated function returns the same singleton
        result_deprecated = create_bigquery_mcp_toolset("any-project-id")
        result_new = get_bigquery_mcp_toolset()

        # Both should return the same singleton instance
        self.assertIs(result_deprecated, result_new)

        # Verify that the project_id parameter is ignored (uses module-level project)
        result_different_project = create_bigquery_mcp_toolset("different-project")
        self.assertIs(result_different_project, result_new)

    def test_singleton_created_at_module_load(self):
        """Test that the MCP toolset singleton is created when the module loads."""
        # Setup registry mock fresh
        mock_registry_module = sys.modules["google.adk.tools.api_registry"]
        mock_registry_cls = mock_registry_module.ApiRegistry

        # Create fresh mock instance
        fresh_mock_instance = MagicMock()
        mock_toolset = MagicMock()
        fresh_mock_instance.get_toolset.return_value = mock_toolset
        fresh_mock_instance.get_toolset.side_effect = None  # Clear any side effects
        mock_registry_cls.return_value = fresh_mock_instance
        mock_registry_cls.reset_mock()

        # Ensure auth returns a valid project
        mock_auth.default.return_value = (MagicMock(), "test-project-id")

        # Clear module cache to force fresh import
        modules_to_remove = [k for k in sys.modules.keys() if k.startswith("trace_analyzer")]
        for mod in modules_to_remove:
            del sys.modules[mod]

        # Import triggers module load, which should create the singleton
        from trace_analyzer import agent

        # Verify get_toolset was called during module load
        # (This happens in _create_module_level_mcp_toolset)
        fresh_mock_instance.get_toolset.assert_called()

        # Verify the MCP server name pattern is correct
        call_kwargs = fresh_mock_instance.get_toolset.call_args
        if call_kwargs:
            # Check that it was called with the expected MCP server name pattern
            call_args, call_kw = call_kwargs
            mcp_server_name = call_kw.get('mcp_server_name', '')
            self.assertIn('mcpServers/google-bigquery.googleapis.com-mcp', mcp_server_name)

    def test_singleton_handles_missing_project_gracefully(self):
        """Test that module-level singleton creation handles missing project ID."""
        # Setup: mock auth to return no project
        mock_auth.default.return_value = (MagicMock(), None)

        # Also ensure GOOGLE_CLOUD_PROJECT is not set
        old_env = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if "GOOGLE_CLOUD_PROJECT" in os.environ:
            del os.environ["GOOGLE_CLOUD_PROJECT"]

        try:
            # Reload agent
            if "trace_analyzer.agent" in sys.modules:
                del sys.modules["trace_analyzer.agent"]

            from trace_analyzer.agent import get_bigquery_mcp_toolset

            # Should return None when no project is available
            result = get_bigquery_mcp_toolset()
            self.assertIsNone(result)
        finally:
            # Restore
            mock_auth.default.return_value = (MagicMock(), "mock-project-id")
            if old_env:
                os.environ["GOOGLE_CLOUD_PROJECT"] = old_env

    def test_singleton_handles_creation_error_gracefully(self):
        """Test that module-level singleton creation handles errors gracefully."""
        mock_registry_module = sys.modules["google.adk.tools.api_registry"]
        mock_registry_cls = mock_registry_module.ApiRegistry

        # Setup mock to raise error during get_toolset
        mock_registry_instance = mock_registry_cls.return_value
        mock_registry_instance.get_toolset.side_effect = Exception("Connection error")

        # Reload agent
        if "trace_analyzer.agent" in sys.modules:
            del sys.modules["trace_analyzer.agent"]

        from trace_analyzer.agent import get_bigquery_mcp_toolset

        # Should return None on error (not raise)
        result = get_bigquery_mcp_toolset()
        self.assertIsNone(result)

        # Cleanup: reset side_effect for other tests
        mock_registry_instance.get_toolset.side_effect = None


if __name__ == "__main__":
    unittest.main()
