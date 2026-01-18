import unittest
from unittest.mock import MagicMock, patch


class TestMCPIntegration(unittest.TestCase):
    @patch("sre_agent.tools.mcp.gcp.ApiRegistry")
    @patch("sre_agent.tools.mcp.gcp.get_current_credentials")
    @patch("sre_agent.tools.mcp.gcp.os.environ")
    def test_create_bigquery_mcp_toolset_returns_toolset(
        self, mock_environ, mock_get_credentials, mock_api_registry_cls
    ):
        """Test that create_bigquery_mcp_toolset creates a toolset when project is available."""
        # Setup mocks
        mock_get_credentials.return_value = (MagicMock(), "mock-project-id")
        mock_environ.get.return_value = "mock-project-id"

        mock_api_registry = MagicMock()
        mock_toolset = MagicMock()
        mock_api_registry.get_toolset.return_value = mock_toolset
        mock_api_registry_cls.return_value = mock_api_registry

        # Import the function (it uses the patched modules since they are in sys.modules)
        # Note: If mcp.py was already loaded, patch updates attributes.
        from sre_agent.tools.mcp.gcp import create_bigquery_mcp_toolset

        # Call the function
        result = create_bigquery_mcp_toolset()

        # Should return the toolset
        self.assertEqual(result, mock_toolset)
        mock_api_registry.get_toolset.assert_called_once()
        from unittest.mock import ANY

        mock_api_registry_cls.assert_called_with("mock-project-id", header_provider=ANY)

    @patch("sre_agent.tools.mcp.gcp.ApiRegistry")
    @patch("sre_agent.tools.mcp.gcp.get_current_credentials")
    @patch("sre_agent.tools.mcp.gcp.os.environ")
    def test_create_bigquery_mcp_toolset_creates_new_instance_each_call(
        self, mock_environ, mock_get_credentials, mock_api_registry_cls
    ):
        """Test that create_bigquery_mcp_toolset returns fresh toolset each time."""
        mock_get_credentials.return_value = (MagicMock(), "mock-project-id")
        mock_environ.get.return_value = "mock-project-id"

        mock_api_registry = MagicMock()
        mock_toolset1 = MagicMock()
        mock_toolset2 = MagicMock()
        mock_api_registry.get_toolset.side_effect = [mock_toolset1, mock_toolset2]
        mock_api_registry_cls.return_value = mock_api_registry

        from sre_agent.tools.mcp.gcp import create_bigquery_mcp_toolset

        # Call twice
        result1 = create_bigquery_mcp_toolset()
        result2 = create_bigquery_mcp_toolset()

        # Should return different instances (not cached)
        self.assertEqual(result1, mock_toolset1)
        self.assertEqual(result2, mock_toolset2)
        # get_toolset should be called twice
        self.assertEqual(mock_api_registry.get_toolset.call_count, 2)

    @patch("sre_agent.tools.mcp.gcp.get_current_credentials")
    @patch("sre_agent.tools.mcp.gcp.os.environ")
    def test_create_bigquery_mcp_toolset_handles_missing_project_gracefully(
        self, mock_environ, mock_get_credentials
    ):
        """Test that create_bigquery_mcp_toolset handles missing project ID."""
        # Setup: mock auth to return no project
        mock_get_credentials.return_value = (MagicMock(), None)
        # Ensure GOOGLE_CLOUD_PROJECT is not set (mock environ)
        mock_environ.get.return_value = None

        from sre_agent.tools.mcp.gcp import create_bigquery_mcp_toolset

        # Should return None when no project is available
        result = create_bigquery_mcp_toolset()
        self.assertIsNone(result)

    @patch("sre_agent.tools.mcp.gcp.ApiRegistry")
    @patch("sre_agent.tools.mcp.gcp.get_current_credentials")
    @patch("sre_agent.tools.mcp.gcp.os.environ")
    def test_create_bigquery_mcp_toolset_raises_on_creation_error(
        self, mock_environ, mock_get_credentials, mock_api_registry_cls
    ):
        """Test that create_bigquery_mcp_toolset raises errors."""
        mock_get_credentials.return_value = (MagicMock(), "mock-project-id")
        mock_environ.get.return_value = "mock-project-id"

        # Setup mock to raise error during get_toolset
        mock_api_registry_cls.return_value.get_toolset.side_effect = RuntimeError(
            "Connection error"
        )

        from sre_agent.tools.mcp.gcp import create_bigquery_mcp_toolset

        # Should raise RuntimeError
        with self.assertRaises(RuntimeError):
            create_bigquery_mcp_toolset()

    def test_mcp_toolset_not_created_at_module_import(self):
        """Test that MCP toolsets are not created just by importing agent."""
        # This test ensures no side-effects import
        # We can mock ApiRegistry global to ensure it is NOT called
        with patch(
            "sre_agent.tools.mcp.gcp.create_bigquery_mcp_toolset"
        ) as mock_create:
            # agent module load should not call create_bigquery_mcp_toolset
            # agent.py calls it lazily in _get_bigquery_mcp_toolset
            mock_create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
