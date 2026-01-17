"""Tool to list GCP projects accessible to the current user."""

import logging
from typing import Any

import google.auth
import google.auth.transport.requests
import httpx

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
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform.read-only"]
        )

        # Refresh credentials if needed
        auth_request = google.auth.transport.requests.Request()
        credentials.refresh(auth_request)  # type: ignore[no-untyped-call]

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
