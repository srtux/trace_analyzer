"""Tool to list GCP projects accessible to the current user."""

import logging
from typing import Any

import google.auth
import google.auth.transport.requests
import httpx

from ...auth import get_current_credentials
from ..common import adk_tool

logger = logging.getLogger(__name__)


@adk_tool
async def list_gcp_projects() -> dict[str, Any]:
    """List GCP projects that the user has access to.

    This tool calls the Cloud Resource Manager API to list projects.

    Returns:
        Dictionary containing a list of projects:
        {
            "projects": [{"id": "project-id", "name": "Project Name"}, ...]
        }
    """
    try:
        credentials, _ = get_current_credentials()

        # If credentials were specifically created from an access token (no refresh),
        # checking .valid might be tricky or unnecessary as it won't have expiry set correctly implies always valid until failed.
        # But if it's default(), it might need refresh.
        # google.auth.default() returns valid credentials usually.

        if not credentials.token:
            # Refresh credentials if needed (only if they support it)
            try:
                auth_request = google.auth.transport.requests.Request()
                credentials.refresh(auth_request)  # type: ignore[no-untyped-call]
            except Exception:
                pass  # Might be an access token credential which doesn't support refresh

        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {credentials.token}"}
            response = await client.get(
                "https://cloudresourcemanager.googleapis.com/v1/projects",
                headers=headers,
            )

            if response.status_code != 200:
                logger.error(f"Failed to list projects: {response.text}")
                return {"projects": [], "error": f"API error: {response.status_code}"}

            data = response.json()
            projects = [
                {"project_id": p["projectId"], "display_name": p["name"]}
                for p in data.get("projects", [])
            ]

            return {"projects": projects}

    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        # Return at least a fallback if possible, but for now we'll just return the error
        return {"projects": [], "error": str(e)}
