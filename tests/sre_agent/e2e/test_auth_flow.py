"""Tests for the authentication middleware and flow."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from server import app
from sre_agent.auth import get_current_credentials_or_none

client = TestClient(app)


def test_auth_middleware_sets_context():
    """Test that Authorization header sets the credentials context."""
    # We need to verify that context var is set during the request.
    # We can create a temporary endpoint to check the context.

    @app.get("/api/test-auth-context")
    async def check_auth_context():
        creds = get_current_credentials_or_none()
        if creds:
            return {"authenticated": True, "token": creds.token}
        return {"authenticated": False}

    # 1. No Header
    response = client.get("/api/test-auth-context")
    assert response.status_code == 200
    assert response.json()["authenticated"] is False

    # 2. With Header
    # Mock Credentials to avoid real validation calls if any (though Credentials struct is simple)
    mock_token = "mock-access-token-123"

    with patch("google.oauth2.credentials.Credentials") as MockCredentials:
        mock_creds_instance = MagicMock()
        mock_creds_instance.token = mock_token
        MockCredentials.return_value = mock_creds_instance

        response = client.get(
            "/api/test-auth-context", headers={"Authorization": f"Bearer {mock_token}"}
        )

        assert response.status_code == 200
        assert response.json()["authenticated"] is True
        assert response.json()["token"] == mock_token


def test_auth_middleware_ignores_invalid_header_format():
    """Test that invalid Authorization headers are ignored."""

    @app.get("/api/test-auth-context-invalid")
    async def check_auth_context_invalid():
        creds = get_current_credentials_or_none()
        return {"authenticated": bool(creds)}

    response = client.get(
        "/api/test-auth-context-invalid", headers={"Authorization": "Basic user:pass"}
    )
    assert response.status_code == 200
    assert response.json()["authenticated"] is False
