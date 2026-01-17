"""Storage Service for SRE Agent.

Provides a unified interface for storing user preferences.
Delegates to ADK session state for persistence.

For local development: Uses DatabaseSessionService (SQLite)
For Agent Engine: Uses VertexAiSessionService
"""

import logging
from typing import Any

from sre_agent.services.session import get_session_service

logger = logging.getLogger(__name__)


class StorageService:
    """High-level storage service for user preferences.

    Uses ADK session state for persistence, which automatically
    selects the appropriate backend based on environment.
    """

    def __init__(self) -> None:
        """Initialize the storage service."""
        self._session_manager = get_session_service()

    async def get_selected_project(self, user_id: str = "default") -> str | None:
        """Get the selected project for a user."""
        return await self._session_manager.get_selected_project(user_id)

    async def set_selected_project(
        self, project_id: str, user_id: str = "default"
    ) -> None:
        """Set the selected project for a user."""
        await self._session_manager.set_selected_project(project_id, user_id)

    async def get_tool_config(
        self, user_id: str = "default"
    ) -> dict[str, bool] | None:
        """Get tool configuration for a user."""
        return await self._session_manager.get_tool_config(user_id)

    async def set_tool_config(
        self, enabled_tools: dict[str, bool], user_id: str = "default"
    ) -> None:
        """Set tool configuration for a user."""
        await self._session_manager.set_tool_config(enabled_tools, user_id)


# ============================================================================
# Singleton Access
# ============================================================================

_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    """Get the singleton StorageService instance."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
