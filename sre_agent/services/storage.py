"""Storage Service for SRE Agent User Preferences.

Provides persistence for user preferences (project selection, tool config).
Uses simple key-value storage - NOT ADK session state.

For local development: JSON file storage
For Cloud Run: Firestore

ADK sessions should be used for conversation history, not preferences.
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

try:
    import google.cloud.firestore as firestore
except ImportError:
    firestore = None

logger = logging.getLogger(__name__)


class PreferencesBackend(ABC):
    """Abstract backend for preferences storage."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Get a preference value."""

    @abstractmethod
    async def set(self, key: str, value: Any) -> None:
        """Set a preference value."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a preference value."""


class FilePreferencesBackend(PreferencesBackend):
    """File-based preferences storage for local development."""

    def __init__(self, file_path: str = ".sre_agent_preferences.json") -> None:
        """Initialize with the file path for storage."""
        self._file_path = Path(file_path)
        self._cache: dict[str, Any] = {}
        self._loaded = False

    def _load(self) -> None:
        """Load preferences from file."""
        if self._loaded:
            return
        if self._file_path.exists():
            try:
                self._cache = json.loads(self._file_path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load preferences: {e}")
                self._cache = {}
        self._loaded = True

    def _save(self) -> None:
        """Save preferences to file."""
        try:
            self._file_path.write_text(json.dumps(self._cache, indent=2))
        except OSError as e:
            logger.error(f"Failed to save preferences: {e}")

    async def get(self, key: str) -> Any | None:
        """Get a preference value from file cache."""
        self._load()
        return self._cache.get(key)

    async def set(self, key: str, value: Any) -> None:
        """Set a preference value in file cache."""
        self._load()
        self._cache[key] = value
        self._save()

    async def delete(self, key: str) -> None:
        """Delete a preference value from file cache."""
        self._load()
        self._cache.pop(key, None)
        self._save()


class FirestorePreferencesBackend(PreferencesBackend):
    """Firestore-based preferences storage for Cloud Run."""

    def __init__(self, collection: str = "user_preferences") -> None:
        """Initialize with Firestore collection name."""
        self._collection = collection
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazy-load Firestore client."""
        if self._client is None and firestore is not None:
            self._client = firestore.AsyncClient()
        return self._client

    async def get(self, key: str) -> Any | None:
        """Get a preference value from Firestore."""
        try:
            client = self._get_client()
            doc = await client.collection(self._collection).document(key).get()
            if doc.exists:
                data = doc.to_dict()
                return data.get("value") if data else None
            return None
        except Exception as e:
            logger.error(f"Firestore get error: {e}")
            return None

    async def set(self, key: str, value: Any) -> None:
        """Set a preference value in Firestore."""
        try:
            client = self._get_client()
            await (
                client.collection(self._collection)
                .document(key)
                .set({"value": value, "updated_at": self._get_timestamp()})
            )
        except Exception as e:
            logger.error(f"Firestore set error: {e}")

    async def delete(self, key: str) -> None:
        """Delete a preference value from Firestore."""
        try:
            client = self._get_client()
            await client.collection(self._collection).document(key).delete()
        except Exception as e:
            logger.error(f"Firestore delete error: {e}")

    @staticmethod
    def _get_timestamp() -> Any:
        if firestore is None:
            return None
        return firestore.SERVER_TIMESTAMP


class StorageService:
    """High-level storage service for user preferences.

    Automatically selects the appropriate backend:
    - Firestore when running on Cloud Run (K_SERVICE env var set)
    - File-based JSON for local development
    """

    # Preference keys
    KEY_SELECTED_PROJECT = "selected_project"
    KEY_TOOL_CONFIG = "tool_config"

    def __init__(self) -> None:
        """Initialize the storage service with appropriate backend."""
        self._backend = self._create_backend()

    def _create_backend(self) -> PreferencesBackend:
        """Create the appropriate backend based on environment."""
        # Cloud Run sets K_SERVICE
        if os.getenv("K_SERVICE") or os.getenv("USE_FIRESTORE"):
            try:
                logger.info("Using Firestore for preferences storage")
                return FirestorePreferencesBackend()
            except Exception as e:
                logger.warning(f"Firestore unavailable, using file storage: {e}")

        logger.info("Using file-based preferences storage")
        return FilePreferencesBackend()

    def _user_key(self, key: str, user_id: str) -> str:
        """Create a user-scoped key."""
        return f"{user_id}:{key}"

    async def get_selected_project(self, user_id: str = "default") -> str | None:
        """Get the selected project for a user."""
        key = self._user_key(self.KEY_SELECTED_PROJECT, user_id)
        result = await self._backend.get(key)
        return result if isinstance(result, str) else None

    async def set_selected_project(
        self, project_id: str, user_id: str = "default"
    ) -> None:
        """Set the selected project for a user."""
        key = self._user_key(self.KEY_SELECTED_PROJECT, user_id)
        await self._backend.set(key, project_id)

    async def get_tool_config(self, user_id: str = "default") -> dict[str, bool] | None:
        """Get tool configuration for a user."""
        key = self._user_key(self.KEY_TOOL_CONFIG, user_id)
        result = await self._backend.get(key)
        return result if isinstance(result, dict) else None

    async def set_tool_config(
        self, enabled_tools: dict[str, bool], user_id: str = "default"
    ) -> None:
        """Set tool configuration for a user."""
        key = self._user_key(self.KEY_TOOL_CONFIG, user_id)
        await self._backend.set(key, enabled_tools)


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
