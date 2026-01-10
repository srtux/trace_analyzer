"""MCP Session Management and Toolset Factories."""

import logging
import os
import google.auth
from google.adk.tools import ToolContext
from google.adk.tools.api_registry import ApiRegistry

logger = logging.getLogger(__name__)


def get_project_id_with_fallback() -> str | None:
    """Get project ID from environment or default credentials."""
    project_id = None
    try:
        _, project_id = google.auth.default()
        project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
    except Exception:
        pass
    return project_id

# Re-exported toolset creation functions will be implemented in specific modules
# but we might want them here or just import them?
# The original mcp.py had them all.
# We will make this the central factory or utilities module.
