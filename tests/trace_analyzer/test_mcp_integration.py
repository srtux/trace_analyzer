import os
import sys
import unittest
from types import ModuleType
from unittest.mock import MagicMock, patch


class TestMCPIntegration(unittest.TestCase):
    def setUp(self):
        # Create mock module hierarchy
        self.mock_google = ModuleType("google")
        self.mock_auth = MagicMock()
        self.mock_auth.default.return_value = (MagicMock(), "mock-project-id")
        self.mock_google.auth = self.mock_auth

        self.mock_adk = MagicMock()

        self.mock_registry_module = ModuleType("google.adk.tools.api_registry")
        self.mock_registry_cls = MagicMock()
        self.mock_registry_module.ApiRegistry = self.mock_registry_cls

        # Prepare the patcher for sys.modules
        self.modules_patcher = patch.dict(
            sys.modules,
            {
                "google": self.mock_google,
                "google.auth": self.mock_auth,
                "google.adk": self.mock_adk,
                "google.adk.agents": self.mock_adk,
                "google.adk.tools": self.mock_adk,
                "google.adk.tools.api_registry": self.mock_registry_module,
                "google.adk.tools.base_toolset": MagicMock(),
                "google.cloud": MagicMock(),
                "google.cloud.trace_v1": MagicMock(),
                "opentelemetry": MagicMock(),
                "opentelemetry.trace": MagicMock(),
                "opentelemetry.metrics": MagicMock(),
                "google.cloud.logging_v2": MagicMock(),
                "google.cloud.logging_v2.services": MagicMock(),
                "google.cloud.logging_v2.services.logging_service_v2": MagicMock(),
                "google.cloud.errorreporting_v1beta1": MagicMock(),
                "google.cloud.monitoring_v3": MagicMock(),
                "numpy": MagicMock(),
                "scipy": MagicMock(),
                "scipy.stats": MagicMock(),
            },
        )
        self.modules_patcher.start()

        # Also clean trace_analyzer from sys.modules to force reload
        self.clean_trace_analyzer_modules()

    def tearDown(self):
        self.modules_patcher.stop()
        self.clean_trace_analyzer_modules()

    def clean_trace_analyzer_modules(self):
        # Remove agent and sub-agents to force reload/re-initialization
        # But KEEP trace_analyzer.tools to avoid split-brain patching in other tests
        for mod in list(sys.modules.keys()):
            if (
                mod == "trace_analyzer"
                or mod == "trace_analyzer.agent"
                or mod.startswith("trace_analyzer.sub_agents")
            ):
                del sys.modules[mod]

    def test_create_bigquery_mcp_toolset_returns_toolset(self):
        """Test that _create_bigquery_mcp_toolset creates a toolset when project is available."""
        # Setup registry mock
        mock_api_registry = MagicMock()
        mock_toolset = MagicMock()
        mock_api_registry.get_toolset.return_value = mock_toolset
        self.mock_registry_cls.return_value = mock_api_registry

        # Import the function
        from trace_analyzer.agent import _create_bigquery_mcp_toolset

        # Call the function
        result = _create_bigquery_mcp_toolset()

        # Should return the toolset
        self.assertEqual(result, mock_toolset)
        mock_api_registry.get_toolset.assert_called_once()

    def test_create_bigquery_mcp_toolset_creates_new_instance_each_call(self):
        """Test that _create_bigquery_mcp_toolset creates new toolsets (no caching)."""
        # Setup registry mock
        mock_api_registry = MagicMock()
        mock_toolset1 = MagicMock()
        mock_toolset2 = MagicMock()
        mock_api_registry.get_toolset.side_effect = [mock_toolset1, mock_toolset2]
        self.mock_registry_cls.return_value = mock_api_registry

        from trace_analyzer.agent import _create_bigquery_mcp_toolset

        # Call twice
        result1 = _create_bigquery_mcp_toolset()
        result2 = _create_bigquery_mcp_toolset()

        # Should return different instances (not cached)
        self.assertEqual(result1, mock_toolset1)
        self.assertEqual(result2, mock_toolset2)
        # get_toolset should be called twice
        self.assertEqual(mock_api_registry.get_toolset.call_count, 2)

    def test_create_bigquery_mcp_toolset_handles_missing_project_gracefully(self):
        """Test that _create_bigquery_mcp_toolset handles missing project ID."""
        # Setup: mock auth to return no project
        self.mock_auth.default.return_value = (MagicMock(), None)

        # Also ensure GOOGLE_CLOUD_PROJECT is not set
        old_env = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if "GOOGLE_CLOUD_PROJECT" in os.environ:
            del os.environ["GOOGLE_CLOUD_PROJECT"]

        try:
            from trace_analyzer.agent import _create_bigquery_mcp_toolset

            # Should return None when no project is available
            result = _create_bigquery_mcp_toolset()
            self.assertIsNone(result)
        finally:
            if old_env:
                os.environ["GOOGLE_CLOUD_PROJECT"] = old_env

    def test_create_bigquery_mcp_toolset_handles_creation_error_gracefully(self):
        """Test that _create_bigquery_mcp_toolset handles errors gracefully."""
        # Setup mock to raise error during get_toolset
        self.mock_registry_cls.return_value.get_toolset.side_effect = Exception(
            "Connection error"
        )

        from trace_analyzer.agent import _create_bigquery_mcp_toolset

        # Should return None on error (not raise)
        result = _create_bigquery_mcp_toolset()
        self.assertIsNone(result)

    def test_mcp_toolset_not_created_at_module_import(self):
        """Test that MCP toolset is NOT created at module import time."""
        # Setup registry mock
        mock_api_registry = MagicMock()
        mock_toolset = MagicMock()
        mock_api_registry.get_toolset.return_value = mock_toolset
        self.mock_registry_cls.return_value = mock_api_registry

        # Import the module
        import trace_analyzer.agent

        # get_toolset should NOT have been called during import
        # (MCP toolset is created lazily in async context, not at module level)
        mock_api_registry.get_toolset.assert_not_called()


if __name__ == "__main__":
    unittest.main()
