"""ADK Session Service Integration for SRE Agent.

Uses ADK's built-in session service implementations:
- DatabaseSessionService: For local development (SQLite)
- VertexAiSessionService: For Agent Engine deployment

Provides persistent session management for conversation history.
User preferences are handled separately by StorageService.
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, cast

from google.adk.events import Event, EventActions
from google.adk.sessions import (
    DatabaseSessionService,
    InMemorySessionService,
    Session,
)

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    """Session information for API responses."""

    id: str
    user_id: str
    app_name: str
    title: str | None = None
    project_id: str | None = None
    created_at: float | None = None
    updated_at: float | None = None
    message_count: int = 0
    preview: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "app_name": self.app_name,
            "title": self.title,
            "project_id": self.project_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count,
            "preview": self.preview,
        }


class ADKSessionManager:
    """Manager for ADK sessions with helper methods.

    Wraps ADK's SessionService with convenience methods for:
    - Session listing and management
    - User preference storage via session state
    - Message history tracking
    """

    APP_NAME = "sre_agent"

    def __init__(self) -> None:
        """Initialize the session manager with appropriate backend."""
        self._session_service = self._create_session_service()
        logger.info(
            f"ADKSessionManager initialized with {type(self._session_service).__name__}"
        )

    def _create_session_service(self) -> Any:
        """Create the appropriate session service based on environment.

        Uses:
        - VertexAiSessionService when SRE_AGENT_ID is set (Agent Engine)
        - DatabaseSessionService for local development (SQLite)
        - InMemorySessionService as fallback
        """
        # Check for Agent Engine deployment
        agent_engine_id = os.getenv("SRE_AGENT_ID")
        if agent_engine_id:
            try:
                from google.adk.sessions import VertexAiSessionService

                project = os.getenv("GOOGLE_CLOUD_PROJECT")
                location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
                if project:
                    logger.info(
                        f"Using VertexAiSessionService for Agent Engine: {agent_engine_id}"
                    )
                    return VertexAiSessionService(
                        project=project,
                        location=location,
                    )
            except Exception as e:
                logger.warning(f"Failed to initialize VertexAiSessionService: {e}")

        # Use SQLite for local persistence
        use_database = os.getenv("USE_DATABASE_SESSIONS", "true").lower() == "true"
        if use_database:
            try:
                db_path = os.getenv("SESSION_DB_PATH", ".sre_agent_sessions.db")
                db_url = f"sqlite+aiosqlite:///{db_path}"
                logger.info(f"Using DatabaseSessionService with SQLite: {db_path}")
                return DatabaseSessionService(db_url=db_url)
            except Exception as e:
                logger.warning(f"Failed to initialize DatabaseSessionService: {e}")

        # Fallback to in-memory
        logger.info("Using InMemorySessionService (no persistence)")
        return InMemorySessionService()  # type: ignore[no-untyped-call]

    @property
    def session_service(self) -> Any:
        """Get the underlying ADK session service."""
        return self._session_service

    async def create_session(
        self,
        user_id: str = "default",
        initial_state: dict[str, Any] | None = None,
    ) -> Session:
        """Create a new session.

        Args:
            user_id: User identifier
            initial_state: Optional initial state dictionary

        Returns:
            The created Session object
        """
        state = initial_state or {}
        state["created_at"] = time.time()

        session = await self._session_service.create_session(
            app_name=self.APP_NAME,
            user_id=user_id,
            state=state,
        )
        logger.info(f"Created session {session.id} for user {user_id}")
        return cast(Session, session)

    async def get_session(
        self,
        session_id: str,
        user_id: str = "default",
    ) -> Session | None:
        """Get a session by ID.

        Args:
            session_id: Session identifier
            user_id: User identifier

        Returns:
            Session object or None if not found
        """
        try:
            session = await self._session_service.get_session(
                app_name=self.APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )
            return cast(Session | None, session)
        except Exception as e:
            logger.warning(f"Failed to get session {session_id}: {e}")
            return None

    async def list_sessions(
        self,
        user_id: str = "default",
    ) -> list[SessionInfo]:
        """List all sessions for a user.

        Args:
            user_id: User identifier

        Returns:
            List of SessionInfo objects
        """
        try:
            sessions = await self._session_service.list_sessions(
                app_name=self.APP_NAME,
                user_id=user_id,
            )

            result = []
            for session in sessions.sessions:
                # Extract info from session
                state = session.state or {}
                events = session.events or []

                # Get preview from first user message
                preview = None
                message_count = 0
                for event in events:
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, "text") and part.text:
                                if event.author == "user":
                                    if not preview:
                                        preview = (
                                            part.text[:100] + "..."
                                            if len(part.text) > 100
                                            else part.text
                                        )
                                message_count += 1

                info = SessionInfo(
                    id=session.id,
                    user_id=user_id,
                    app_name=self.APP_NAME,
                    title=state.get("title"),
                    project_id=state.get("project_id"),
                    created_at=state.get("created_at"),
                    updated_at=session.last_update_time,
                    message_count=message_count,
                    preview=preview,
                )
                result.append(info)

            # Sort by updated_at descending
            result.sort(key=lambda x: x.updated_at or 0, reverse=True)
            return result

        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []

    async def delete_session(
        self,
        session_id: str,
        user_id: str = "default",
    ) -> bool:
        """Delete a session.

        Args:
            session_id: Session identifier
            user_id: User identifier

        Returns:
            True if deleted successfully
        """
        try:
            await self._session_service.delete_session(
                app_name=self.APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )
            logger.info(f"Deleted session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    async def update_session_state(
        self,
        session: Session,
        state_delta: dict[str, Any],
    ) -> None:
        """Update session state using proper event-based approach.

        Args:
            session: The session to update
            state_delta: Dictionary of state changes
        """
        actions = EventActions(state_delta=state_delta)
        event = Event(
            invocation_id=f"state-update-{time.time()}",
            author="system",
            actions=actions,
            timestamp=time.time(),
        )
        await self._session_service.append_event(session, event)
        logger.debug(f"Updated session {session.id} state: {list(state_delta.keys())}")

    async def get_or_create_session(
        self,
        session_id: str | None = None,
        user_id: str = "default",
        project_id: str | None = None,
    ) -> Session:
        """Get existing session or create a new one.

        Args:
            session_id: Optional session ID to retrieve
            user_id: User identifier
            project_id: Optional project ID for context

        Returns:
            Session object
        """
        if session_id:
            session = await self.get_session(session_id, user_id)
            if session:
                return session

        # Create new session with initial state
        initial_state = {}
        if project_id:
            initial_state["project_id"] = project_id

        return await self.create_session(user_id=user_id, initial_state=initial_state)


# ============================================================================
# Singleton Access
# ============================================================================

_session_manager: ADKSessionManager | None = None


def get_session_service() -> ADKSessionManager:
    """Get the singleton ADKSessionManager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = ADKSessionManager()
    return _session_manager
