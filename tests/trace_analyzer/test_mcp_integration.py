
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from types import ModuleType

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
        self.modules_patcher = patch.dict(sys.modules, {
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
        })
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
            if mod == "trace_analyzer" or mod == "trace_analyzer.agent" or mod.startswith("trace_analyzer.sub_agents"):
                del sys.modules[mod]

    def test_singleton_created_lazily(self):
        """Test that the MCP toolset singleton is created LAZILY, not at import time."""
        # Setup registry mock
        fresh_mock_instance = MagicMock()
        mock_toolset = MagicMock()
        fresh_mock_instance.get_toolset.return_value = mock_toolset
        self.mock_registry_cls.return_value = fresh_mock_instance
        
        # Import triggers module load
        import trace_analyzer.agent
        
        # KEY ASSERTION: Registry should NOT be called at import time anymore
        self.mock_registry_cls.assert_not_called()
        fresh_mock_instance.get_toolset.assert_not_called()
        
        # Call the getter
        result = trace_analyzer.agent.get_bigquery_mcp_toolset()
        
        # NOW it should be called
        self.mock_registry_cls.assert_called_once()
        fresh_mock_instance.get_toolset.assert_called_once()
        
        # Call it again -> should not be called again (memoized)
        result2 = trace_analyzer.agent.get_bigquery_mcp_toolset()
        self.assertIs(result, result2)
        fresh_mock_instance.get_toolset.assert_called_once()

    def test_module_level_toolset_singleton(self):
        """Test that the module-level MCP toolset singleton is created correctly."""
        mock_toolset = MagicMock()
        mock_registry_instance = self.mock_registry_cls.return_value
        mock_registry_instance.get_toolset.return_value = mock_toolset
        
        import trace_analyzer.agent
    
        # Inspect the module object directly to see the global var update
        # Initially None
        self.assertIsNone(trace_analyzer.agent._bigquery_mcp_toolset)
        
        # Verify get_bigquery_mcp_toolset returns dict or object and updates global
        result = trace_analyzer.agent.get_bigquery_mcp_toolset()
        self.assertIsNotNone(result)
        self.assertIs(result, trace_analyzer.agent._bigquery_mcp_toolset)

    def test_get_bigquery_mcp_toolset_returns_singleton(self):
        """Test that get_bigquery_mcp_toolset() always returns the same instance."""
        from trace_analyzer.agent import get_bigquery_mcp_toolset
    
        # Call multiple times - should always return the same instance
        result1 = get_bigquery_mcp_toolset()
        result2 = get_bigquery_mcp_toolset()
        result3 = get_bigquery_mcp_toolset()
    
        self.assertIsNotNone(result1)
        self.assertIs(result1, result2)
        self.assertIs(result2, result3)

    def test_create_bigquery_mcp_toolset_deprecated_returns_singleton(self):
        """Test that deprecated create_bigquery_mcp_toolset returns the singleton."""
        mock_toolset = MagicMock()
        self.mock_registry_cls.return_value.get_toolset.return_value = mock_toolset
    
        from trace_analyzer.agent import create_bigquery_mcp_toolset, get_bigquery_mcp_toolset
    
        # Test: deprecated function returns the same singleton
        # Calling create_... should also trigger lazy loads if not loaded
        result_deprecated = create_bigquery_mcp_toolset("any-project-id")
        result_new = get_bigquery_mcp_toolset()
        
        self.assertIsNotNone(result_deprecated)
        self.assertIs(result_deprecated, result_new)
    
        # Verify that the project_id parameter is ignored (uses module-level project)
        result_different_project = create_bigquery_mcp_toolset("different-project")
        self.assertIs(result_different_project, result_new)

    def test_singleton_handles_missing_project_gracefully(self):
        """Test that module-level singleton creation handles missing project ID."""
        # Setup: mock auth to return no project
        self.mock_auth.default.return_value = (MagicMock(), None)
    
        # Also ensure GOOGLE_CLOUD_PROJECT is not set
        old_env = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if "GOOGLE_CLOUD_PROJECT" in os.environ:
            del os.environ["GOOGLE_CLOUD_PROJECT"]
    
        try:
            from trace_analyzer.agent import get_bigquery_mcp_toolset
    
            # Should return None when no project is available
            result = get_bigquery_mcp_toolset()
            self.assertIsNone(result)
        finally:
            if old_env:
                os.environ["GOOGLE_CLOUD_PROJECT"] = old_env

    def test_singleton_handles_creation_error_gracefully(self):
        """Test that module-level singleton creation handles errors gracefully."""
        # Setup mock to raise error during get_toolset
        self.mock_registry_cls.return_value.get_toolset.side_effect = Exception("Connection error")
    
        from trace_analyzer.agent import get_bigquery_mcp_toolset
    
        # Should return None on error (not raise)
        result = get_bigquery_mcp_toolset()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
