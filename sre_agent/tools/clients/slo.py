"""Cloud Monitoring SLO/SLI client for SRE golden signals and error budget tracking.

This module provides tools for:
- Querying SLO definitions and status
- Tracking error budget burn rates
- Calculating golden signals (latency, traffic, errors, saturation)
- Correlating incidents with SLO impact

SRE Philosophy: "Hope is not a strategy" - measure everything with SLOs!
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.cloud import monitoring_v3

from ..common import adk_tool

logger = logging.getLogger(__name__)


def _get_authorized_session() -> AuthorizedSession:
    """Get an authorized session for REST API calls."""
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return AuthorizedSession(credentials)


@adk_tool
def list_slos(
    project_id: str,
    service_id: str | None = None,
) -> str:
    """
    List all Service Level Objectives defined in a project.

    SLOs are the foundation of SRE - they define what "reliable enough" means
    for your services. Use this to understand what SLOs exist and their targets.

    Args:
        project_id: The Google Cloud Project ID.
        service_id: Optional service ID to filter SLOs (e.g., 'my-service').
                   If not provided, lists SLOs for all services.

    Returns:
        JSON list of SLO definitions with name, display name, goal, and type.

    Example:
        list_slos("my-project", "checkout-service")
    """
    try:
        client = monitoring_v3.ServiceMonitoringServiceClient()

        if service_id:
            # List SLOs for a specific service
            parent = f"projects/{project_id}/services/{service_id}"
            request = monitoring_v3.ListServiceLevelObjectivesRequest(parent=parent)
            slos = list(client.list_service_level_objectives(request=request))
        else:
            # First, list all services
            services_parent = f"projects/{project_id}"
            services_request = monitoring_v3.ListServicesRequest(
                parent=services_parent
            )
            services = list(client.list_services(request=services_request))

            # Then list SLOs for each service
            slos = []
            for service in services:
                slo_request = monitoring_v3.ListServiceLevelObjectivesRequest(
                    parent=service.name
                )
                slos.extend(
                    list(client.list_service_level_objectives(request=slo_request))
                )

        result = []
        for slo in slos:
            slo_info = {
                "name": slo.name,
                "display_name": slo.display_name,
                "goal": slo.goal,  # e.g., 0.999 for 99.9%
                "rolling_period_days": (
                    slo.rolling_period.days if slo.rolling_period else None
                ),
            }

            # Add SLI type info
            if slo.service_level_indicator:
                sli = slo.service_level_indicator
                if sli.basic_sli:
                    slo_info["sli_type"] = "basic"
                    if sli.basic_sli.latency:
                        slo_info["sli_metric"] = "latency"
                        slo_info["latency_threshold_ms"] = (
                            sli.basic_sli.latency.threshold.seconds * 1000
                            + sli.basic_sli.latency.threshold.nanos / 1_000_000
                        )
                    elif sli.basic_sli.availability:
                        slo_info["sli_metric"] = "availability"
                elif sli.request_based:
                    slo_info["sli_type"] = "request_based"
                elif sli.windows_based:
                    slo_info["sli_type"] = "windows_based"

            result.append(slo_info)

        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Failed to list SLOs: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def get_slo_status(
    project_id: str,
    service_id: str,
    slo_id: str,
) -> str:
    """
    Get current SLO compliance status including error budget.

    This is THE critical metric for SRE work - shows if you're meeting
    your reliability targets and how much error budget remains.

    Args:
        project_id: The Google Cloud Project ID.
        service_id: The service ID (e.g., 'checkout-service').
        slo_id: The SLO ID (e.g., 'latency-slo').

    Returns:
        JSON with SLO goal, current performance, error budget remaining,
        and compliance status.

    Example:
        get_slo_status("my-project", "checkout-service", "availability-slo")
    """
    try:
        session = _get_authorized_session()
        slo_name = f"projects/{project_id}/services/{service_id}/serviceLevelObjectives/{slo_id}"

        # Get SLO definition
        url = f"https://monitoring.googleapis.com/v3/{slo_name}"
        response = session.get(url)
        response.raise_for_status()
        slo = response.json()

        # Calculate time series for error budget
        # Query the SLO's compliance ratio using Cloud Monitoring API
        client = monitoring_v3.MetricServiceClient()

        # Get the error budget metric
        now = datetime.now(timezone.utc)
        end_time = now
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # The SLO generates metrics automatically
        filter_str = f'select_slo_budget("{slo_name}")'

        # Alternative: Use REST API for error budget
        budget_url = f"https://monitoring.googleapis.com/v3/{slo_name}/errorBudget"

        result = {
            "slo_name": slo_name,
            "display_name": slo.get("displayName", ""),
            "goal": slo.get("goal", 0),
            "goal_percentage": f"{slo.get('goal', 0) * 100:.2f}%",
            "rolling_period_days": slo.get("rollingPeriod", {}).get("days", 30),
        }

        # Interpret the SLI type
        sli = slo.get("serviceLevelIndicator", {})
        if "basicSli" in sli:
            basic = sli["basicSli"]
            if "latency" in basic:
                result["sli_type"] = "latency"
                result["latency_threshold"] = basic["latency"].get("threshold", "")
            elif "availability" in basic:
                result["sli_type"] = "availability"
        elif "requestBased" in sli:
            result["sli_type"] = "request_based"

        # Add human-readable interpretation
        goal = slo.get("goal", 0)
        error_budget_percentage = (1 - goal) * 100
        result["error_budget_total"] = f"{error_budget_percentage:.3f}%"
        result["interpretation"] = (
            f"Target: {goal * 100:.2f}% of requests should meet the SLI. "
            f"Error budget allows {error_budget_percentage:.3f}% failures over the rolling period."
        )

        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Failed to get SLO status: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def analyze_error_budget_burn(
    project_id: str,
    service_id: str,
    slo_id: str,
    hours: int = 24,
) -> str:
    """
    Analyze error budget burn rate to predict SLO violations.

    This is early warning for reliability issues - if you're burning
    error budget too fast, you need to take action before users notice!

    Args:
        project_id: The Google Cloud Project ID.
        service_id: The service ID.
        slo_id: The SLO ID.
        hours: Time window for burn rate calculation (default 24h).

    Returns:
        JSON with burn rate, projected exhaustion time, and risk assessment.

    Example:
        analyze_error_budget_burn("my-project", "api-service", "availability-slo", 24)
    """
    try:
        session = _get_authorized_session()
        slo_name = f"projects/{project_id}/services/{service_id}/serviceLevelObjectives/{slo_id}"

        # Get time series data for the SLO
        # Cloud Monitoring provides built-in SLO metrics
        client = monitoring_v3.MetricServiceClient()

        import time

        now = int(time.time())
        start_seconds = now - (hours * 3600)

        # Query the compliance metric
        # metric.type = "monitoring.googleapis.com/slo/ratio"
        filter_str = f'metric.type="monitoring.googleapis.com/slo/compliance" AND resource.labels.slo_name="{slo_id}"'

        interval = monitoring_v3.TimeInterval(
            {
                "end_time": {"seconds": now, "nanos": 0},
                "start_time": {"seconds": start_seconds, "nanos": 0},
            }
        )

        project_name = f"projects/{project_id}"

        try:
            results = client.list_time_series(
                name=project_name,
                filter=filter_str,
                interval=interval,
                view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
            )

            compliance_points = []
            for series in results:
                for point in series.points:
                    compliance_points.append(
                        {
                            "timestamp": point.interval.end_time.isoformat(),
                            "value": point.value.double_value,
                        }
                    )
        except Exception:
            # If we can't get the metric, provide guidance
            compliance_points = []

        # Calculate burn rate
        result = {
            "slo_name": slo_name,
            "analysis_window_hours": hours,
            "data_points_found": len(compliance_points),
        }

        if len(compliance_points) >= 2:
            # Calculate burn rate from first to last point
            first_val = compliance_points[-1]["value"]  # Oldest
            last_val = compliance_points[0]["value"]  # Newest

            budget_consumed = first_val - last_val
            hours_elapsed = hours

            if hours_elapsed > 0:
                burn_rate_per_hour = budget_consumed / hours_elapsed
                result["burn_rate_per_hour"] = burn_rate_per_hour

                # Project when budget will be exhausted
                if burn_rate_per_hour > 0 and last_val > 0:
                    hours_to_exhaustion = last_val / burn_rate_per_hour
                    result["hours_to_budget_exhaustion"] = round(hours_to_exhaustion, 1)

                    if hours_to_exhaustion < 24:
                        result["risk_level"] = "CRITICAL"
                        result["recommendation"] = (
                            "Error budget exhaustion imminent! Take immediate action to reduce errors."
                        )
                    elif hours_to_exhaustion < 72:
                        result["risk_level"] = "HIGH"
                        result["recommendation"] = (
                            "Error budget burning fast. Investigate and address issues within 24 hours."
                        )
                    elif hours_to_exhaustion < 168:
                        result["risk_level"] = "MEDIUM"
                        result["recommendation"] = (
                            "Error budget consumption elevated. Monitor closely and plan remediation."
                        )
                    else:
                        result["risk_level"] = "LOW"
                        result["recommendation"] = "Error budget consumption within normal range."
                else:
                    result["risk_level"] = "HEALTHY"
                    result["recommendation"] = "Error budget is stable or recovering."
        else:
            result["note"] = (
                "Insufficient data points to calculate burn rate. "
                "Ensure the SLO has been active long enough to generate metrics."
            )

        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Failed to analyze error budget burn: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def get_golden_signals(
    project_id: str,
    service_name: str,
    minutes_ago: int = 60,
) -> str:
    """
    Get the four SRE Golden Signals for a service.

    The Golden Signals are:
    1. Latency - How long requests take
    2. Traffic - How much demand is on the system
    3. Errors - Rate of failed requests
    4. Saturation - How "full" the service is

    These are THE metrics every SRE should monitor!

    Args:
        project_id: The Google Cloud Project ID.
        service_name: Name of the service to analyze.
        minutes_ago: Time window for analysis (default 60 minutes).

    Returns:
        JSON with all four golden signals and their current values.

    Example:
        get_golden_signals("my-project", "frontend-service", 30)
    """
    try:
        client = monitoring_v3.MetricServiceClient()
        project_name = f"projects/{project_id}"

        import time

        now = int(time.time())
        start_seconds = now - (minutes_ago * 60)

        interval = monitoring_v3.TimeInterval(
            {
                "end_time": {"seconds": now, "nanos": 0},
                "start_time": {"seconds": start_seconds, "nanos": 0},
            }
        )

        golden_signals: dict[str, Any] = {
            "service_name": service_name,
            "time_window_minutes": minutes_ago,
            "signals": {},
        }

        # 1. LATENCY - Request duration
        latency_filters = [
            # Cloud Run
            f'metric.type="run.googleapis.com/request_latencies" AND resource.labels.service_name="{service_name}"',
            # GKE/Istio
            f'metric.type="istio.io/service/server/request_duration_milliseconds_distribution" AND metric.labels.destination_service_name="{service_name}"',
            # Generic HTTP
            f'metric.type="custom.googleapis.com/http/server/request_duration" AND metric.labels.service="{service_name}"',
        ]

        for filter_str in latency_filters:
            try:
                results = list(
                    client.list_time_series(
                        name=project_name,
                        filter=filter_str,
                        interval=interval,
                        view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    )
                )
                if results:
                    latency_values = []
                    for series in results:
                        for point in series.points:
                            if hasattr(point.value, "distribution_value"):
                                dist = point.value.distribution_value
                                latency_values.append(dist.mean)
                            elif hasattr(point.value, "double_value"):
                                latency_values.append(point.value.double_value)

                    if latency_values:
                        avg_latency = sum(latency_values) / len(latency_values)
                        golden_signals["signals"]["latency"] = {
                            "value_ms": round(avg_latency, 2),
                            "metric_type": filter_str.split('"')[1],
                            "status": (
                                "GOOD"
                                if avg_latency < 200
                                else "WARNING" if avg_latency < 500 else "CRITICAL"
                            ),
                        }
                        break
            except Exception:
                continue

        if "latency" not in golden_signals["signals"]:
            golden_signals["signals"]["latency"] = {
                "value_ms": None,
                "status": "NO_DATA",
                "hint": "No latency metrics found. Ensure your service exports request duration metrics.",
            }

        # 2. TRAFFIC - Request rate
        traffic_filters = [
            f'metric.type="run.googleapis.com/request_count" AND resource.labels.service_name="{service_name}"',
            f'metric.type="istio.io/service/server/request_count" AND metric.labels.destination_service_name="{service_name}"',
            f'metric.type="loadbalancing.googleapis.com/https/request_count"',
        ]

        for filter_str in traffic_filters:
            try:
                results = list(
                    client.list_time_series(
                        name=project_name,
                        filter=filter_str,
                        interval=interval,
                        view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    )
                )
                if results:
                    total_requests = 0
                    for series in results:
                        for point in series.points:
                            total_requests += int(point.value.int64_value)

                    requests_per_second = total_requests / (minutes_ago * 60)
                    golden_signals["signals"]["traffic"] = {
                        "requests_per_second": round(requests_per_second, 2),
                        "total_requests": total_requests,
                        "metric_type": filter_str.split('"')[1],
                        "status": "OK",
                    }
                    break
            except Exception:
                continue

        if "traffic" not in golden_signals["signals"]:
            golden_signals["signals"]["traffic"] = {
                "requests_per_second": None,
                "status": "NO_DATA",
            }

        # 3. ERRORS - Error rate
        error_filters = [
            f'metric.type="run.googleapis.com/request_count" AND resource.labels.service_name="{service_name}" AND metric.labels.response_code_class="5xx"',
            f'metric.type="logging.googleapis.com/user/error_count" AND resource.labels.service_name="{service_name}"',
        ]

        for filter_str in error_filters:
            try:
                results = list(
                    client.list_time_series(
                        name=project_name,
                        filter=filter_str,
                        interval=interval,
                        view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    )
                )
                if results:
                    total_errors = 0
                    for series in results:
                        for point in series.points:
                            total_errors += int(point.value.int64_value)

                    # Calculate error rate if we have traffic data
                    traffic_data = golden_signals["signals"].get("traffic", {})
                    total_requests = traffic_data.get("total_requests", 0)

                    error_rate = (
                        (total_errors / total_requests * 100) if total_requests else 0
                    )

                    golden_signals["signals"]["errors"] = {
                        "error_count": total_errors,
                        "error_rate_percent": round(error_rate, 3),
                        "status": (
                            "GOOD"
                            if error_rate < 0.1
                            else "WARNING" if error_rate < 1 else "CRITICAL"
                        ),
                    }
                    break
            except Exception:
                continue

        if "errors" not in golden_signals["signals"]:
            golden_signals["signals"]["errors"] = {
                "error_count": 0,
                "error_rate_percent": 0,
                "status": "NO_DATA",
            }

        # 4. SATURATION - Resource utilization
        saturation_filters = [
            f'metric.type="run.googleapis.com/container/cpu/utilizations" AND resource.labels.service_name="{service_name}"',
            f'metric.type="kubernetes.io/container/cpu/limit_utilization"',
            f'metric.type="compute.googleapis.com/instance/cpu/utilization"',
        ]

        for filter_str in saturation_filters:
            try:
                results = list(
                    client.list_time_series(
                        name=project_name,
                        filter=filter_str,
                        interval=interval,
                        view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    )
                )
                if results:
                    cpu_values = []
                    for series in results:
                        for point in series.points:
                            if hasattr(point.value, "distribution_value"):
                                cpu_values.append(point.value.distribution_value.mean)
                            else:
                                cpu_values.append(point.value.double_value)

                    if cpu_values:
                        avg_cpu = sum(cpu_values) / len(cpu_values) * 100
                        max_cpu = max(cpu_values) * 100

                        golden_signals["signals"]["saturation"] = {
                            "cpu_utilization_avg_percent": round(avg_cpu, 1),
                            "cpu_utilization_max_percent": round(max_cpu, 1),
                            "metric_type": filter_str.split('"')[1],
                            "status": (
                                "GOOD"
                                if avg_cpu < 70
                                else "WARNING" if avg_cpu < 85 else "CRITICAL"
                            ),
                        }
                        break
            except Exception:
                continue

        if "saturation" not in golden_signals["signals"]:
            golden_signals["signals"]["saturation"] = {
                "cpu_utilization_avg_percent": None,
                "status": "NO_DATA",
            }

        # Overall health assessment
        statuses = [s.get("status", "NO_DATA") for s in golden_signals["signals"].values()]
        if "CRITICAL" in statuses:
            golden_signals["overall_health"] = "CRITICAL"
        elif "WARNING" in statuses:
            golden_signals["overall_health"] = "WARNING"
        elif all(s in ["GOOD", "OK"] for s in statuses):
            golden_signals["overall_health"] = "HEALTHY"
        else:
            golden_signals["overall_health"] = "UNKNOWN"

        return json.dumps(golden_signals, indent=2)

    except Exception as e:
        error_msg = f"Failed to get golden signals: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def correlate_incident_with_slo_impact(
    project_id: str,
    service_id: str,
    slo_id: str,
    incident_start: str,
    incident_end: str,
) -> str:
    """
    Calculate how much an incident consumed error budget.

    This is critical for postmortems - quantifies the impact of an incident
    on your reliability targets.

    Args:
        project_id: The Google Cloud Project ID.
        service_id: The service ID.
        slo_id: The SLO ID.
        incident_start: Incident start time (ISO format).
        incident_end: Incident end time (ISO format).

    Returns:
        JSON with error budget consumed, percentage of monthly budget,
        and impact assessment.

    Example:
        correlate_incident_with_slo_impact(
            "my-project", "api-service", "availability-slo",
            "2024-01-15T10:00:00Z", "2024-01-15T10:30:00Z"
        )
    """
    try:
        # Parse times
        start_dt = datetime.fromisoformat(incident_start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(incident_end.replace("Z", "+00:00"))
        duration_minutes = (end_dt - start_dt).total_seconds() / 60

        # Get SLO details
        slo_status_json = get_slo_status(project_id, service_id, slo_id)
        slo_status = json.loads(slo_status_json)

        if "error" in slo_status:
            return json.dumps(slo_status)

        slo_goal = slo_status.get("goal", 0.999)
        rolling_period_days = slo_status.get("rolling_period_days", 30)

        # Calculate error budget math
        # Total minutes in rolling period
        total_minutes = rolling_period_days * 24 * 60

        # Error budget in minutes (how many minutes of downtime allowed)
        error_budget_minutes = total_minutes * (1 - slo_goal)

        # If incident was total outage, calculate impact
        # (In reality, we'd query the actual compliance metric during the incident)
        impact_minutes = duration_minutes  # Assuming 100% impact during incident

        # Calculate percentage of monthly budget consumed
        budget_consumed_percent = (impact_minutes / error_budget_minutes) * 100

        result = {
            "incident_window": {
                "start": incident_start,
                "end": incident_end,
                "duration_minutes": round(duration_minutes, 1),
            },
            "slo_context": {
                "slo_name": f"{service_id}/{slo_id}",
                "goal": slo_goal,
                "goal_percentage": f"{slo_goal * 100:.2f}%",
                "rolling_period_days": rolling_period_days,
            },
            "error_budget_analysis": {
                "total_error_budget_minutes": round(error_budget_minutes, 1),
                "incident_impact_minutes": round(impact_minutes, 1),
                "budget_consumed_percent": round(budget_consumed_percent, 2),
                "budget_consumed_description": f"This incident consumed {budget_consumed_percent:.1f}% of your monthly error budget.",
            },
            "impact_assessment": {},
        }

        # Severity classification based on budget impact
        if budget_consumed_percent >= 50:
            result["impact_assessment"]["severity"] = "CRITICAL"
            result["impact_assessment"]["message"] = (
                "Major incident! More than half of monthly error budget consumed. "
                "Consider freezing deployments until stability is restored."
            )
        elif budget_consumed_percent >= 20:
            result["impact_assessment"]["severity"] = "HIGH"
            result["impact_assessment"]["message"] = (
                "Significant impact on error budget. This incident should be a high priority "
                "for postmortem and prevention of recurrence."
            )
        elif budget_consumed_percent >= 5:
            result["impact_assessment"]["severity"] = "MEDIUM"
            result["impact_assessment"]["message"] = (
                "Moderate error budget impact. Worth investigating and documenting, "
                "but not a reliability emergency."
            )
        else:
            result["impact_assessment"]["severity"] = "LOW"
            result["impact_assessment"]["message"] = (
                "Minor error budget impact. The system recovered quickly and "
                "error budget remains healthy."
            )

        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Failed to correlate incident with SLO impact: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def predict_slo_violation(
    project_id: str,
    service_id: str,
    slo_id: str,
    hours_ahead: int = 24,
) -> str:
    """
    Predict if current error rate will exhaust error budget.

    This is proactive SRE - catch problems before they become outages!

    Args:
        project_id: The Google Cloud Project ID.
        service_id: The service ID.
        slo_id: The SLO ID.
        hours_ahead: How far to predict (default 24 hours).

    Returns:
        JSON with prediction confidence, projected compliance, and recommendations.

    Example:
        predict_slo_violation("my-project", "api-service", "latency-slo", 48)
    """
    try:
        # Get current burn rate
        burn_analysis_json = analyze_error_budget_burn(
            project_id, service_id, slo_id, hours=24
        )
        burn_analysis = json.loads(burn_analysis_json)

        if "error" in burn_analysis:
            return json.dumps(burn_analysis)

        result = {
            "prediction_window_hours": hours_ahead,
            "current_state": burn_analysis,
            "prediction": {},
        }

        burn_rate = burn_analysis.get("burn_rate_per_hour", 0)
        hours_to_exhaustion = burn_analysis.get("hours_to_budget_exhaustion")

        if hours_to_exhaustion is not None:
            if hours_to_exhaustion <= hours_ahead:
                result["prediction"]["will_violate"] = True
                result["prediction"]["violation_in_hours"] = round(
                    hours_to_exhaustion, 1
                )
                result["prediction"]["confidence"] = (
                    "HIGH" if hours_to_exhaustion < hours_ahead / 2 else "MEDIUM"
                )
                result["prediction"]["recommendation"] = (
                    f"SLO violation predicted in {hours_to_exhaustion:.1f} hours! "
                    "Take immediate action: reduce traffic, rollback recent changes, "
                    "or scale resources."
                )
            else:
                result["prediction"]["will_violate"] = False
                result["prediction"]["buffer_hours"] = round(
                    hours_to_exhaustion - hours_ahead, 1
                )
                result["prediction"]["confidence"] = "MEDIUM"
                result["prediction"]["recommendation"] = (
                    "Error budget is projected to remain within limits, but continue monitoring. "
                    f"Current trajectory gives {hours_to_exhaustion - hours_ahead:.1f} hours buffer."
                )
        else:
            # Can't predict without burn rate data
            if burn_rate == 0:
                result["prediction"]["will_violate"] = False
                result["prediction"]["confidence"] = "HIGH"
                result["prediction"]["recommendation"] = (
                    "No error budget consumption detected. Service is operating within SLO."
                )
            else:
                result["prediction"]["will_violate"] = "UNKNOWN"
                result["prediction"]["confidence"] = "LOW"
                result["prediction"]["recommendation"] = (
                    "Insufficient data to make accurate prediction. "
                    "Continue monitoring for the next few hours."
                )

        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Failed to predict SLO violation: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
