import pytest

from sre_agent.services.session import ADKSessionManager, SessionInfo


@pytest.mark.asyncio
async def test_session_manager_in_memory():
    """Test that session manager works with in-memory service."""
    # Force in-memory for testing
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("USE_DATABASE_SESSIONS", "false")
        mp.delenv("SRE_AGENT_ID", raising=False)

        manager = ADKSessionManager()
        assert "InMemorySessionService" in str(type(manager.session_service))

        # Test create session
        session = await manager.create_session(
            user_id="test-user", initial_state={"foo": "bar"}
        )
        assert session.id is not None
        assert session.state["foo"] == "bar"
        assert "created_at" in session.state

        # Test get session
        retrieved = await manager.get_session(session.id, user_id="test-user")
        assert retrieved.id == session.id

        # Test list sessions
        sessions = await manager.list_sessions(user_id="test-user")
        assert len(sessions) == 1
        assert sessions[0].id == session.id
        assert sessions[0].user_id == "test-user"

        # Test update state
        await manager.update_session_state(session, {"new_key": "new_val"})
        updated = await manager.get_session(session.id, user_id="test-user")
        assert updated.state["new_key"] == "new_val"

        # Test delete session
        success = await manager.delete_session(session.id, user_id="test-user")
        assert success is True

        not_found = await manager.get_session(session.id, user_id="test-user")
        assert not_found is None


def test_session_info_to_dict():
    """Test SessionInfo conversion to dict."""
    info = SessionInfo(
        id="s1",
        user_id="u1",
        app_name="app",
        title="Title",
        project_id="p1",
        created_at=123456789.0,
        updated_at=123456790.0,
        message_count=5,
        preview="Hello",
    )
    d = info.to_dict()
    assert d["id"] == "s1"
    assert d["title"] == "Title"
    assert d["message_count"] == 5
    assert d["preview"] == "Hello"


@pytest.mark.asyncio
async def test_storage_service():
    """Test StorageService delegation."""
    from sre_agent.services.storage import get_storage_service

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("USE_DATABASE_SESSIONS", "false")

        storage = get_storage_service()

        # Test project selection
        await storage.set_selected_project("test-proj", user_id="u2")
        proj = await storage.get_selected_project(user_id="u2")
        assert proj == "test-proj"

        # Test tool config
        config = {"tool1": True, "tool2": False}
        await storage.set_tool_config(config, user_id="u2")
        retrieved = await storage.get_tool_config(user_id="u2")
        assert retrieved == config
