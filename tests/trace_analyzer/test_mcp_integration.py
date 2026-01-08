
import os
import sys
import unittest
from unittest.mock import MagicMock, patch



# Mock google.adk components
mock_adk = MagicMock()
sys.modules["google.adk"] = mock_adk
sys.modules["google.adk.agents"] = mock_adk
sys.modules["google.adk.tools"] = mock_adk
sys.modules["google.adk.tools.api_registry"] = MagicMock() # Mock the registry module
sys.modules["google.adk.tools.base_toolset"] = MagicMock() 
class MockBaseToolset:
    pass
sys.modules["google.adk.tools.base_toolset"].BaseToolset = MockBaseToolset

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

    def test_load_mcp_tools_registry(self):
        # We'll use the mock we injected into sys.modules
        mock_registry_module = sys.modules["google.adk.tools.api_registry"]
        mock_registry_cls = mock_registry_module.ApiRegistry

        # Reset mocks
        mock_registry_cls.reset_mock()

        # Reload agent to ensure it picks up the mocks and runs clean
        if "trace_analyzer.agent" in sys.modules:
            del sys.modules["trace_analyzer.agent"]
        from trace_analyzer.agent import load_mcp_tools

        # Setup registry mock instance interactions
        mock_registry_instance = mock_registry_cls.return_value
        mock_registry_instance.get_toolset.return_value = ["bq_tool_1", "bq_tool_2"]

        tools = load_mcp_tools()

        # Check if LazyMcpRegistryToolset is in tools
        lazy_toolset = next((t for t in tools if type(t).__name__ == 'LazyMcpRegistryToolset'), None)
        self.assertIsNotNone(lazy_toolset)



if __name__ == "__main__":
    unittest.main()
