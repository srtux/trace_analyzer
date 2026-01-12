"""Direct API client for Cloud Monitoring Alerts."""

import json
import logging
from typing import Any

import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.cloud import monitoring_v3

from ..common import adk_tool
from ..common.telemetry import get_tracer
from .factory import get_alert_policy_client

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


@adk_tool
def list_alerts(
    project_id: str,
    filter_str: str | None = None,
    order_by: str | None = None,
    page_size: int = 100,
) -> str:
    """Lists alerts (incidents) using the Google Cloud Monitoring API.

    Args:
        project_id: The Google Cloud Project ID.
        filter_str: Optional filter string (e.g., 'state="OPEN"').
        order_by: Optional sort order field.
        page_size: Number of results to return (default 100).

    Returns:
        A JSON string containing the list of alerts.
    """
    with tracer.start_as_current_span("list_alerts") as span:
        span.set_attribute("gcp.project_id", project_id)
        if filter_str:
            span.set_attribute("gcp.monitoring.filter", filter_str)

        try:
            # Get credentials
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            session = AuthorizedSession(credentials)  # type: ignore[no-untyped-call]

            # API Endpoint: projects.alerts.list
            # https://cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.alerts/list
            url = f"https://monitoring.googleapis.com/v3/projects/{project_id}/alerts"

            params: dict[str, Any] = {"pageSize": page_size}
            if filter_str:
                params["filter"] = filter_str
            if order_by:
                params["orderBy"] = order_by

            response = session.get(url, params=params)
            response.raise_for_status()

            alerts = response.json().get("alerts", [])
            span.set_attribute("gcp.monitoring.alerts_count", len(alerts))
            return json.dumps(alerts)

        except Exception as e:
            span.record_exception(e)
            error_msg = f"Failed to list alerts: {e!s}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({"error": error_msg})


@adk_tool
def get_alert(name: str) -> str:
    """Gets a specific alert by its resource name.

    Args:
        name: The resource name of the alert
              (e.g., projects/{project_id}/alerts/{alert_id}).

    Returns:
        A JSON string containing the alert details.
    """
    with tracer.start_as_current_span("get_alert") as span:
        span.set_attribute("gcp.monitoring.alert_name", name)

        try:
            # Get credentials
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            session = AuthorizedSession(credentials)  # type: ignore[no-untyped-call]

            # API Endpoint: projects.alerts.get
            url = f"https://monitoring.googleapis.com/v3/{name}"

            response = session.get(url)
            response.raise_for_status()

            return json.dumps(response.json())

        except Exception as e:
            span.record_exception(e)
            error_msg = f"Failed to get alert: {e!s}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({"error": error_msg})


@adk_tool
def list_alert_policies(
    project_id: str,
    filter_str: str | None = None,
    page_size: int = 100,
) -> str:
    """Lists alert policies from Google Cloud Monitoring.

    Args:
        project_id: The Google Cloud Project ID.
        filter_str: Optional filter string.
        page_size: Number of results to return.

    Returns:
        A JSON string containing the list of alert policies.
    """
    with tracer.start_as_current_span("list_alert_policies") as span:
        span.set_attribute("gcp.project_id", project_id)

        try:
            client = get_alert_policy_client()
            project_name = f"projects/{project_id}"

            request = monitoring_v3.ListAlertPoliciesRequest(
                name=project_name,
                filter=filter_str if filter_str else "",
                page_size=page_size,
            )

            results = client.list_alert_policies(request=request)

            # Convert protobuf results to list of dicts
            policies_data = []
            for policy in results:
                # Basic fields + user_labels
                policy_dict = {
                    "name": policy.name,
                    "display_name": policy.display_name,
                    "documentation": {
                        "content": policy.documentation.content,
                        "mime_type": policy.documentation.mime_type,
                    },
                    "user_labels": dict(policy.user_labels),
                    "conditions": [],
                    "enabled": policy.enabled,
                }

                # Extract simple condition info
                for condition in policy.conditions:
                    policy_dict["conditions"].append(
                        {
                            "name": condition.name,
                            "display_name": condition.display_name,
                        }
                    )

                policies_data.append(policy_dict)

            span.set_attribute("gcp.monitoring.policies_count", len(policies_data))
            return json.dumps(policies_data)

        except Exception as e:
            span.record_exception(e)
            error_msg = f"Failed to list alert policies: {e!s}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({"error": error_msg})
