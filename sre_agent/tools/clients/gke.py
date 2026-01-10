"""GKE (Google Kubernetes Engine) client for Kubernetes-specific debugging.

This module provides tools for:
- Pod status and container health analysis
- Node pressure and resource conditions
- HPA (Horizontal Pod Autoscaler) events and decisions
- Workload troubleshooting

Kubernetes Wisdom: "Cattle, not pets" - but we still care when the herd is sick!
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
def get_gke_cluster_health(
    project_id: str,
    cluster_name: str,
    location: str,
) -> str:
    """
    Get comprehensive GKE cluster health status.

    This is your cluster's vital signs - node status, control plane health,
    and any ongoing issues that could affect workloads.

    Args:
        project_id: The Google Cloud Project ID.
        cluster_name: Name of the GKE cluster.
        location: Cluster location (zone or region, e.g., 'us-central1-a' or 'us-central1').

    Returns:
        JSON with cluster status, node pool health, and any active issues.

    Example:
        get_gke_cluster_health("my-project", "prod-cluster", "us-central1")
    """
    try:
        session = _get_authorized_session()

        # GKE Container API endpoint
        url = f"https://container.googleapis.com/v1/projects/{project_id}/locations/{location}/clusters/{cluster_name}"

        response = session.get(url)
        response.raise_for_status()
        cluster = response.json()

        result: dict[str, Any] = {
            "cluster_name": cluster.get("name"),
            "location": cluster.get("location"),
            "status": cluster.get("status"),
            "current_master_version": cluster.get("currentMasterVersion"),
            "current_node_version": cluster.get("currentNodeVersion"),
        }

        # Check cluster status
        status = cluster.get("status", "")
        if status == "RUNNING":
            result["health"] = "HEALTHY"
        elif status == "RECONCILING":
            result["health"] = "UPDATING"
            result["health_message"] = "Cluster is being updated or repaired"
        elif status == "DEGRADED":
            result["health"] = "DEGRADED"
            result["health_message"] = "Cluster is experiencing issues"
        else:
            result["health"] = status

        # Node pools status
        node_pools = cluster.get("nodePools", [])
        result["node_pools"] = []

        for pool in node_pools:
            pool_info = {
                "name": pool.get("name"),
                "status": pool.get("status"),
                "machine_type": pool.get("config", {}).get("machineType"),
                "initial_node_count": pool.get("initialNodeCount"),
                "autoscaling": pool.get("autoscaling", {}).get("enabled", False),
            }

            if pool.get("autoscaling", {}).get("enabled"):
                pool_info["min_nodes"] = pool["autoscaling"].get("minNodeCount", 0)
                pool_info["max_nodes"] = pool["autoscaling"].get("maxNodeCount", 0)

            # Check for upgrade in progress
            if pool.get("status") == "RECONCILING":
                pool_info["upgrade_in_progress"] = True

            result["node_pools"].append(pool_info)

        # Check for any conditions
        conditions = cluster.get("conditions", [])
        if conditions:
            result["active_conditions"] = []
            for cond in conditions:
                if cond.get("status") != "True":
                    result["active_conditions"].append(
                        {
                            "type": cond.get("type"),
                            "status": cond.get("status"),
                            "message": cond.get("message"),
                        }
                    )

        # Add maintenance info
        maintenance = cluster.get("maintenancePolicy", {})
        if maintenance:
            result["maintenance_window"] = maintenance.get("window", {})

        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Failed to get GKE cluster health: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def analyze_node_conditions(
    project_id: str,
    cluster_name: str,
    location: str,
    node_name: str | None = None,
) -> str:
    """
    Check for node pressure conditions (CPU, Memory, Disk, PID).

    Node pressure conditions are early warnings that your nodes are struggling.
    Catch these before pods start getting evicted!

    Args:
        project_id: The Google Cloud Project ID.
        cluster_name: Name of the GKE cluster.
        location: Cluster location.
        node_name: Specific node to check (optional, checks all if not provided).

    Returns:
        JSON with node conditions and any pressure warnings.

    Example:
        analyze_node_conditions("my-project", "prod-cluster", "us-central1-a")
    """
    try:
        # Query Cloud Monitoring for node conditions
        client = monitoring_v3.MetricServiceClient()
        project_name = f"projects/{project_id}"

        import time

        now = int(time.time())
        start_seconds = now - 3600  # Last hour

        interval = monitoring_v3.TimeInterval(
            {
                "end_time": {"seconds": now, "nanos": 0},
                "start_time": {"seconds": start_seconds, "nanos": 0},
            }
        )

        result: dict[str, Any] = {
            "cluster": cluster_name,
            "location": location,
            "nodes": {},
            "pressure_warnings": [],
        }

        # Key metrics to check for node health
        metrics_to_check = [
            (
                "kubernetes.io/node/cpu/allocatable_utilization",
                "cpu_utilization",
                0.85,
            ),
            (
                "kubernetes.io/node/memory/allocatable_utilization",
                "memory_utilization",
                0.85,
            ),
            ("kubernetes.io/node/ephemeral_storage/used_bytes", "disk_used", None),
            (
                "kubernetes.io/node/ephemeral_storage/total_bytes",
                "disk_total",
                None,
            ),
            ("kubernetes.io/node/pid/limit", "pid_limit", None),
            ("kubernetes.io/node/pid/used", "pid_used", None),
        ]

        for metric_type, metric_name, threshold in metrics_to_check:
            filter_str = f'metric.type="{metric_type}"'
            if node_name:
                filter_str += f' AND resource.labels.node_name="{node_name}"'

            try:
                results = list(
                    client.list_time_series(
                        name=project_name,
                        filter=filter_str,
                        interval=interval,
                        view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    )
                )

                for series in results:
                    node = series.resource.labels.get("node_name", "unknown")

                    if node not in result["nodes"]:
                        result["nodes"][node] = {"metrics": {}, "conditions": []}

                    # Get the most recent value
                    if series.points:
                        latest = series.points[0]
                        value = latest.value.double_value or latest.value.int64_value

                        result["nodes"][node]["metrics"][metric_name] = value

                        # Check thresholds
                        if threshold and value > threshold:
                            condition = {
                                "type": f"{metric_name}_pressure",
                                "value": round(value * 100 if value < 1 else value, 1),
                                "threshold": threshold * 100 if threshold < 1 else threshold,
                                "severity": "WARNING" if value < 0.95 else "CRITICAL",
                            }
                            result["nodes"][node]["conditions"].append(condition)
                            result["pressure_warnings"].append(
                                {
                                    "node": node,
                                    "condition": condition,
                                }
                            )

            except Exception as e:
                logger.debug(f"Could not fetch {metric_name}: {e}")
                continue

        # Calculate disk utilization
        for node, data in result["nodes"].items():
            metrics = data["metrics"]
            if "disk_used" in metrics and "disk_total" in metrics:
                disk_util = metrics["disk_used"] / metrics["disk_total"]
                metrics["disk_utilization"] = round(disk_util * 100, 1)

                if disk_util > 0.85:
                    condition = {
                        "type": "disk_pressure",
                        "value": round(disk_util * 100, 1),
                        "threshold": 85,
                        "severity": "WARNING" if disk_util < 0.95 else "CRITICAL",
                    }
                    data["conditions"].append(condition)
                    result["pressure_warnings"].append({"node": node, "condition": condition})

            # PID pressure
            if "pid_used" in metrics and "pid_limit" in metrics:
                pid_util = metrics["pid_used"] / metrics["pid_limit"]
                metrics["pid_utilization"] = round(pid_util * 100, 1)

                if pid_util > 0.80:
                    condition = {
                        "type": "pid_pressure",
                        "value": round(pid_util * 100, 1),
                        "threshold": 80,
                        "severity": "WARNING" if pid_util < 0.90 else "CRITICAL",
                    }
                    data["conditions"].append(condition)
                    result["pressure_warnings"].append({"node": node, "condition": condition})

        # Summary
        total_nodes = len(result["nodes"])
        nodes_with_pressure = len(set(w["node"] for w in result["pressure_warnings"]))

        result["summary"] = {
            "total_nodes": total_nodes,
            "nodes_with_pressure": nodes_with_pressure,
            "health": (
                "CRITICAL" if nodes_with_pressure > total_nodes * 0.5
                else "WARNING" if nodes_with_pressure > 0
                else "HEALTHY"
            ),
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Failed to analyze node conditions: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def get_pod_restart_events(
    project_id: str,
    namespace: str | None = None,
    pod_name: str | None = None,
    minutes_ago: int = 60,
) -> str:
    """
    Find pods with high restart counts or recent restarts.

    Pod restarts are often the first sign of trouble - OOMKilled, CrashLoopBackOff,
    liveness probe failures, etc.

    Args:
        project_id: The Google Cloud Project ID.
        namespace: Kubernetes namespace to filter (optional).
        pod_name: Specific pod name to check (optional).
        minutes_ago: Time window to check (default 60 minutes).

    Returns:
        JSON with pods that have restarted and their restart reasons.

    Example:
        get_pod_restart_events("my-project", "production", minutes_ago=30)
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

        # Query container restart count metric
        filter_str = 'metric.type="kubernetes.io/container/restart_count"'
        if namespace:
            filter_str += f' AND resource.labels.namespace_name="{namespace}"'
        if pod_name:
            filter_str += f' AND resource.labels.pod_name="{pod_name}"'

        results = list(
            client.list_time_series(
                name=project_name,
                filter=filter_str,
                interval=interval,
                view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
            )
        )

        pod_restarts: dict[str, Any] = {}

        for series in results:
            labels = series.resource.labels
            pod_key = f"{labels.get('namespace_name', 'default')}/{labels.get('pod_name', 'unknown')}"
            container = labels.get("container_name", "unknown")

            if series.points:
                # Compare first and last points to get restart count in window
                oldest = series.points[-1].value.int64_value
                newest = series.points[0].value.int64_value
                restarts_in_window = newest - oldest

                if restarts_in_window > 0 or newest > 0:
                    if pod_key not in pod_restarts:
                        pod_restarts[pod_key] = {
                            "namespace": labels.get("namespace_name"),
                            "pod_name": labels.get("pod_name"),
                            "cluster": labels.get("cluster_name"),
                            "containers": {},
                            "total_restarts_in_window": 0,
                        }

                    pod_restarts[pod_key]["containers"][container] = {
                        "restart_count_total": newest,
                        "restarts_in_window": restarts_in_window,
                    }
                    pod_restarts[pod_key]["total_restarts_in_window"] += restarts_in_window

        # Sort by most restarts
        sorted_pods = sorted(
            pod_restarts.values(),
            key=lambda x: x["total_restarts_in_window"],
            reverse=True,
        )

        result = {
            "time_window_minutes": minutes_ago,
            "pods_with_restarts": sorted_pods[:20],  # Top 20
            "summary": {
                "total_pods_with_restarts": len(sorted_pods),
                "total_restarts": sum(p["total_restarts_in_window"] for p in sorted_pods),
            },
        }

        # Add severity assessment
        if result["summary"]["total_restarts"] > 50:
            result["severity"] = "CRITICAL"
            result["message"] = "High number of pod restarts detected! Check for OOMKilled or CrashLoopBackOff."
        elif result["summary"]["total_restarts"] > 10:
            result["severity"] = "WARNING"
            result["message"] = "Elevated pod restart activity. Investigate the top restarting pods."
        else:
            result["severity"] = "NORMAL"
            result["message"] = "Pod restart activity within normal range."

        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Failed to get pod restart events: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def analyze_hpa_events(
    project_id: str,
    namespace: str,
    deployment_name: str,
    minutes_ago: int = 60,
) -> str:
    """
    Analyze HorizontalPodAutoscaler scaling events and decisions.

    HPAs are how Kubernetes handles load, but they can also cause problems
    when misconfigured or when scaling is too slow.

    Args:
        project_id: The Google Cloud Project ID.
        namespace: Kubernetes namespace.
        deployment_name: Name of the deployment with HPA.
        minutes_ago: Time window to analyze (default 60 minutes).

    Returns:
        JSON with scaling events, current/desired replicas, and recommendations.

    Example:
        analyze_hpa_events("my-project", "production", "frontend-deploy", 120)
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

        result: dict[str, Any] = {
            "namespace": namespace,
            "deployment": deployment_name,
            "time_window_minutes": minutes_ago,
            "scaling_activity": [],
            "current_state": {},
        }

        # Query replica count metrics
        replica_metrics = [
            ("kubernetes.io/deployment/replicas", "current_replicas"),
            ("kubernetes.io/deployment/desired_replicas", "desired_replicas"),
        ]

        for metric_type, metric_name in replica_metrics:
            filter_str = (
                f'metric.type="{metric_type}" '
                f'AND resource.labels.namespace_name="{namespace}" '
                f'AND resource.labels.deployment_name="{deployment_name}"'
            )

            try:
                results = list(
                    client.list_time_series(
                        name=project_name,
                        filter=filter_str,
                        interval=interval,
                        view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    )
                )

                if results and results[0].points:
                    points = results[0].points
                    values = [p.value.int64_value for p in points]

                    result["current_state"][metric_name] = points[0].value.int64_value
                    result[f"{metric_name}_min"] = min(values)
                    result[f"{metric_name}_max"] = max(values)

                    # Detect scaling events (when value changed)
                    for i in range(len(points) - 1):
                        if points[i].value.int64_value != points[i + 1].value.int64_value:
                            event = {
                                "timestamp": points[i].interval.end_time.isoformat(),
                                "metric": metric_name,
                                "from": points[i + 1].value.int64_value,
                                "to": points[i].value.int64_value,
                                "direction": "scale_up" if points[i].value.int64_value > points[i + 1].value.int64_value else "scale_down",
                            }
                            result["scaling_activity"].append(event)

            except Exception as e:
                logger.debug(f"Could not fetch {metric_name}: {e}")

        # Sort scaling events by time
        result["scaling_activity"].sort(key=lambda x: x["timestamp"], reverse=True)

        # Count scaling events
        scale_ups = sum(1 for e in result["scaling_activity"] if e["direction"] == "scale_up")
        scale_downs = sum(1 for e in result["scaling_activity"] if e["direction"] == "scale_down")

        result["summary"] = {
            "total_scaling_events": len(result["scaling_activity"]),
            "scale_up_count": scale_ups,
            "scale_down_count": scale_downs,
        }

        # Recommendations
        if len(result["scaling_activity"]) > 20:
            result["recommendation"] = (
                "High scaling frequency detected (thrashing). Consider:\n"
                "1. Increasing stabilization window\n"
                "2. Adjusting scaling thresholds\n"
                "3. Checking for oscillating load patterns"
            )
        elif scale_ups > 0 and result.get("current_replicas_max") == result.get("desired_replicas_max"):
            result["recommendation"] = (
                "HPA reached maximum replicas during this period. "
                "Consider increasing maxReplicas if capacity is needed."
            )
        elif len(result["scaling_activity"]) == 0:
            result["recommendation"] = (
                "No scaling events in this period. HPA is stable or not triggering. "
                "Verify HPA metrics are being collected."
            )
        else:
            result["recommendation"] = "HPA activity appears normal."

        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Failed to analyze HPA events: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def get_container_oom_events(
    project_id: str,
    namespace: str | None = None,
    minutes_ago: int = 60,
) -> str:
    """
    Find containers that were OOMKilled (Out of Memory).

    OOMKilled is one of the most common causes of container restarts.
    This helps identify memory leaks or undersized containers.

    Args:
        project_id: The Google Cloud Project ID.
        namespace: Kubernetes namespace to filter (optional).
        minutes_ago: Time window to check (default 60 minutes).

    Returns:
        JSON with containers that experienced OOM events and memory usage patterns.

    Example:
        get_container_oom_events("my-project", "production", 120)
    """
    try:
        # First, check for OOM events in logs
        session = _get_authorized_session()

        from urllib.parse import quote

        # Build log filter for OOM events
        log_filter = 'resource.type="k8s_container" AND textPayload:"OOMKilled"'
        if namespace:
            log_filter += f' AND resource.labels.namespace_name="{namespace}"'

        now = datetime.now(timezone.utc)
        timestamp = now.isoformat()

        # Use Cloud Logging API
        url = f"https://logging.googleapis.com/v2/entries:list"
        body = {
            "resourceNames": [f"projects/{project_id}"],
            "filter": log_filter,
            "orderBy": "timestamp desc",
            "pageSize": 100,
        }

        try:
            response = session.post(url, json=body)
            response.raise_for_status()
            log_data = response.json()
            oom_logs = log_data.get("entries", [])
        except Exception:
            oom_logs = []

        # Also query memory usage to find containers near limit
        client = monitoring_v3.MetricServiceClient()
        project_name = f"projects/{project_id}"

        import time

        now_ts = int(time.time())
        start_seconds = now_ts - (minutes_ago * 60)

        interval = monitoring_v3.TimeInterval(
            {
                "end_time": {"seconds": now_ts, "nanos": 0},
                "start_time": {"seconds": start_seconds, "nanos": 0},
            }
        )

        # Query memory usage vs limit
        filter_str = 'metric.type="kubernetes.io/container/memory/limit_utilization"'
        if namespace:
            filter_str += f' AND resource.labels.namespace_name="{namespace}"'

        high_memory_containers = []

        try:
            results = list(
                client.list_time_series(
                    name=project_name,
                    filter=filter_str,
                    interval=interval,
                    view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                )
            )

            for series in results:
                labels = series.resource.labels
                if series.points:
                    max_util = max(p.value.double_value for p in series.points)
                    avg_util = sum(p.value.double_value for p in series.points) / len(series.points)

                    if max_util > 0.85:  # >85% memory utilization
                        high_memory_containers.append({
                            "namespace": labels.get("namespace_name"),
                            "pod": labels.get("pod_name"),
                            "container": labels.get("container_name"),
                            "max_memory_utilization": round(max_util * 100, 1),
                            "avg_memory_utilization": round(avg_util * 100, 1),
                            "risk_level": "HIGH" if max_util > 0.95 else "MEDIUM",
                        })

        except Exception as e:
            logger.debug(f"Could not fetch memory utilization: {e}")

        # Sort by utilization
        high_memory_containers.sort(key=lambda x: x["max_memory_utilization"], reverse=True)

        result = {
            "time_window_minutes": minutes_ago,
            "oom_events_in_logs": len(oom_logs),
            "containers_at_risk": high_memory_containers[:15],
            "oom_log_samples": [],
        }

        # Add sample OOM log entries
        for entry in oom_logs[:5]:
            result["oom_log_samples"].append({
                "timestamp": entry.get("timestamp"),
                "pod": entry.get("resource", {}).get("labels", {}).get("pod_name"),
                "container": entry.get("resource", {}).get("labels", {}).get("container_name"),
                "message": entry.get("textPayload", "")[:200],
            })

        # Recommendations
        if len(oom_logs) > 0:
            result["severity"] = "CRITICAL"
            result["recommendation"] = (
                f"Found {len(oom_logs)} OOMKilled events! Actions:\n"
                "1. Increase memory limits for affected containers\n"
                "2. Check for memory leaks in application code\n"
                "3. Consider vertical pod autoscaling (VPA)"
            )
        elif len(high_memory_containers) > 0:
            result["severity"] = "WARNING"
            result["recommendation"] = (
                f"Found {len(high_memory_containers)} containers with high memory usage. "
                "These may OOMKill soon. Consider increasing memory limits proactively."
            )
        else:
            result["severity"] = "NORMAL"
            result["recommendation"] = "No OOM events or high memory utilization detected."

        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Failed to get OOM events: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def correlate_trace_with_kubernetes(
    project_id: str,
    trace_id: str,
    cluster_name: str | None = None,
) -> str:
    """
    Link a distributed trace to Kubernetes pod and container context.

    This bridges the gap between application traces and infrastructure -
    when a trace is slow, find out WHICH pod handled it and what its state was.

    Args:
        project_id: The Google Cloud Project ID.
        trace_id: The trace ID to correlate.
        cluster_name: Optional cluster name to filter.

    Returns:
        JSON with pod info, container status, and resource usage during the trace.

    Example:
        correlate_trace_with_kubernetes("my-project", "abc123def456", "prod-cluster")
    """
    try:
        # First, get the trace to find the time window and service names
        from ..trace import fetch_trace

        trace_json = fetch_trace(project_id, trace_id)
        trace_data = json.loads(trace_json)

        if "error" in trace_data:
            return trace_json

        spans = trace_data.get("spans", [])
        if not spans:
            return json.dumps({"error": "No spans found in trace"})

        # Find time window
        start_times = []
        end_times = []
        services = set()

        for span in spans:
            start_times.append(span.get("start_time", ""))
            end_times.append(span.get("end_time", ""))
            # Extract service name from span name or attributes
            span_name = span.get("name", "")
            if "/" in span_name:
                services.add(span_name.split("/")[0])
            for attr in span.get("attributes", {}).get("attribute_map", {}).values():
                if "service" in str(attr).lower():
                    services.add(str(attr))

        if start_times:
            trace_start = min(start_times)
            trace_end = max(end_times)
        else:
            return json.dumps({"error": "Could not determine trace time window"})

        result = {
            "trace_id": trace_id,
            "trace_window": {
                "start": trace_start,
                "end": trace_end,
            },
            "services_in_trace": list(services),
            "kubernetes_context": [],
        }

        # Query Cloud Logging for pod info during trace window
        session = _get_authorized_session()

        # Look for logs with this trace ID
        log_filter = f'trace="projects/{project_id}/traces/{trace_id}"'

        url = "https://logging.googleapis.com/v2/entries:list"
        body = {
            "resourceNames": [f"projects/{project_id}"],
            "filter": log_filter,
            "orderBy": "timestamp desc",
            "pageSize": 50,
        }

        try:
            response = session.post(url, json=body)
            response.raise_for_status()
            log_data = response.json()

            pods_seen = set()
            for entry in log_data.get("entries", []):
                resource = entry.get("resource", {})
                labels = resource.get("labels", {})

                if resource.get("type") in ["k8s_container", "k8s_pod"]:
                    pod_key = f"{labels.get('namespace_name')}/{labels.get('pod_name')}"
                    if pod_key not in pods_seen:
                        pods_seen.add(pod_key)
                        result["kubernetes_context"].append({
                            "namespace": labels.get("namespace_name"),
                            "pod_name": labels.get("pod_name"),
                            "container_name": labels.get("container_name"),
                            "cluster": labels.get("cluster_name"),
                        })

        except Exception as e:
            logger.debug(f"Could not query logs for trace: {e}")

        # Summary
        if result["kubernetes_context"]:
            result["summary"] = (
                f"Trace {trace_id} was processed by {len(result['kubernetes_context'])} "
                f"Kubernetes pods/containers."
            )
        else:
            result["summary"] = (
                "Could not find Kubernetes pod information for this trace. "
                "Ensure your application logs include trace context."
            )

        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Failed to correlate trace with Kubernetes: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def get_workload_health_summary(
    project_id: str,
    namespace: str,
    minutes_ago: int = 30,
) -> str:
    """
    Get a comprehensive health summary for all workloads in a namespace.

    This is your "dashboard view" of namespace health - see at a glance
    which workloads are healthy and which need attention.

    Args:
        project_id: The Google Cloud Project ID.
        namespace: Kubernetes namespace to analyze.
        minutes_ago: Time window for analysis (default 30 minutes).

    Returns:
        JSON with workload health status, resource usage, and issues.

    Example:
        get_workload_health_summary("my-project", "production", 60)
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

        workloads: dict[str, Any] = {}

        # Query key metrics for the namespace
        metrics = [
            ("kubernetes.io/container/cpu/limit_utilization", "cpu_util"),
            ("kubernetes.io/container/memory/limit_utilization", "memory_util"),
            ("kubernetes.io/container/restart_count", "restarts"),
        ]

        for metric_type, metric_key in metrics:
            filter_str = (
                f'metric.type="{metric_type}" '
                f'AND resource.labels.namespace_name="{namespace}"'
            )

            try:
                results = list(
                    client.list_time_series(
                        name=project_name,
                        filter=filter_str,
                        interval=interval,
                        view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    )
                )

                for series in results:
                    labels = series.resource.labels
                    pod_name = labels.get("pod_name", "unknown")

                    # Extract deployment name from pod name (common pattern: deploy-name-hash-hash)
                    parts = pod_name.rsplit("-", 2)
                    workload_name = parts[0] if len(parts) >= 3 else pod_name

                    if workload_name not in workloads:
                        workloads[workload_name] = {
                            "name": workload_name,
                            "namespace": namespace,
                            "pods": set(),
                            "cpu_util_max": 0,
                            "memory_util_max": 0,
                            "total_restarts": 0,
                            "issues": [],
                        }

                    workloads[workload_name]["pods"].add(pod_name)

                    if series.points:
                        if metric_key == "cpu_util":
                            val = max(p.value.double_value for p in series.points)
                            workloads[workload_name]["cpu_util_max"] = max(
                                workloads[workload_name]["cpu_util_max"], val
                            )
                        elif metric_key == "memory_util":
                            val = max(p.value.double_value for p in series.points)
                            workloads[workload_name]["memory_util_max"] = max(
                                workloads[workload_name]["memory_util_max"], val
                            )
                        elif metric_key == "restarts":
                            oldest = series.points[-1].value.int64_value
                            newest = series.points[0].value.int64_value
                            workloads[workload_name]["total_restarts"] += newest - oldest

            except Exception as e:
                logger.debug(f"Could not fetch {metric_key}: {e}")

        # Analyze each workload
        result_workloads = []
        critical_count = 0
        warning_count = 0

        for name, data in workloads.items():
            workload = {
                "name": name,
                "namespace": namespace,
                "pod_count": len(data["pods"]),
                "cpu_utilization_max": round(data["cpu_util_max"] * 100, 1),
                "memory_utilization_max": round(data["memory_util_max"] * 100, 1),
                "restarts_in_window": data["total_restarts"],
                "status": "HEALTHY",
                "issues": [],
            }

            # Determine health status
            if data["total_restarts"] > 5:
                workload["status"] = "CRITICAL"
                workload["issues"].append(f"High restart count: {data['total_restarts']}")
                critical_count += 1
            elif data["memory_util_max"] > 0.95:
                workload["status"] = "CRITICAL"
                workload["issues"].append("Memory near limit (>95%)")
                critical_count += 1
            elif data["cpu_util_max"] > 0.95:
                workload["status"] = "WARNING"
                workload["issues"].append("CPU near limit (>95%)")
                warning_count += 1
            elif data["memory_util_max"] > 0.85:
                workload["status"] = "WARNING"
                workload["issues"].append("High memory usage (>85%)")
                warning_count += 1
            elif data["total_restarts"] > 0:
                workload["status"] = "WARNING"
                workload["issues"].append(f"Restarts detected: {data['total_restarts']}")
                warning_count += 1

            result_workloads.append(workload)

        # Sort by status (critical first)
        status_order = {"CRITICAL": 0, "WARNING": 1, "HEALTHY": 2}
        result_workloads.sort(key=lambda x: status_order.get(x["status"], 3))

        result = {
            "namespace": namespace,
            "time_window_minutes": minutes_ago,
            "summary": {
                "total_workloads": len(workloads),
                "critical": critical_count,
                "warning": warning_count,
                "healthy": len(workloads) - critical_count - warning_count,
                "overall_health": (
                    "CRITICAL" if critical_count > 0
                    else "WARNING" if warning_count > 0
                    else "HEALTHY"
                ),
            },
            "workloads": result_workloads,
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Failed to get workload health summary: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
