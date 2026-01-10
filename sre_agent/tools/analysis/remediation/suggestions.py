"""Automated remediation suggestion engine.

This module analyzes findings from SRE investigations and generates
actionable remediation suggestions. It's like having a senior SRE's
experience encoded into recommendations.

Philosophy: "Move from diagnosis to treatment" - don't just tell users
what's wrong, tell them how to fix it!
"""

import json
import logging
from typing import Any

from ...common import adk_tool

logger = logging.getLogger(__name__)


# Remediation knowledge base - patterns to fixes
REMEDIATION_PATTERNS = {
    # Memory issues
    "oom_killed": {
        "pattern": ["OOMKilled", "out of memory", "memory limit"],
        "category": "memory",
        "severity": "high",
        "suggestions": [
            {
                "action": "Increase memory limits",
                "description": "The container is exceeding its memory limit and being killed by the OOM killer.",
                "steps": [
                    "Review current memory usage patterns",
                    "Increase memory limit by 25-50%",
                    "Monitor for continued OOMs",
                ],
                "risk": "low",
                "effort": "low",
            },
            {
                "action": "Investigate memory leaks",
                "description": "Repeated OOMs may indicate a memory leak in the application.",
                "steps": [
                    "Enable memory profiling (Cloud Profiler)",
                    "Check for growing heap size over time",
                    "Review recent code changes for leak patterns",
                ],
                "risk": "medium",
                "effort": "high",
            },
            {
                "action": "Enable Vertical Pod Autoscaler",
                "description": "VPA can automatically adjust memory limits based on usage.",
                "steps": [
                    "Install VPA in the cluster",
                    "Create VPA resource for the workload",
                    "Start with 'Off' mode to get recommendations",
                ],
                "risk": "medium",
                "effort": "medium",
            },
        ],
    },
    # CPU throttling
    "cpu_throttling": {
        "pattern": ["cpu throttl", "cpu limit", "cpu saturat"],
        "category": "cpu",
        "severity": "medium",
        "suggestions": [
            {
                "action": "Increase CPU limits",
                "description": "Container is being CPU throttled, causing latency.",
                "steps": [
                    "Review CPU utilization metrics",
                    "Increase CPU limit (not request) by 50%",
                    "Monitor throttling metrics",
                ],
                "risk": "low",
                "effort": "low",
            },
            {
                "action": "Optimize CPU-intensive code",
                "description": "High CPU usage may indicate inefficient algorithms.",
                "steps": [
                    "Use Cloud Profiler to find CPU hotspots",
                    "Profile and optimize hot code paths",
                    "Consider async processing for heavy tasks",
                ],
                "risk": "medium",
                "effort": "high",
            },
        ],
    },
    # Connection pool exhaustion
    "connection_pool": {
        "pattern": [
            "connection pool",
            "pool exhausted",
            "max connections",
            "connection timeout",
        ],
        "category": "database",
        "severity": "high",
        "suggestions": [
            {
                "action": "Increase connection pool size",
                "description": "Application is running out of database connections.",
                "steps": [
                    "Check current pool size configuration",
                    "Increase pool size (consider DB max connections)",
                    "Add connection pool metrics to monitoring",
                ],
                "risk": "low",
                "effort": "low",
            },
            {
                "action": "Fix connection leaks",
                "description": "Connections may not be properly returned to pool.",
                "steps": [
                    "Review code for proper connection handling (try-finally)",
                    "Add connection leak detection logging",
                    "Ensure connections are closed in error paths",
                ],
                "risk": "medium",
                "effort": "medium",
            },
            {
                "action": "Add connection pooling middleware",
                "description": "Use PgBouncer or similar for connection management.",
                "steps": [
                    "Deploy PgBouncer/ProxySQL in front of database",
                    "Configure pool mode (transaction/session/statement)",
                    "Update application connection strings",
                ],
                "risk": "medium",
                "effort": "high",
            },
        ],
    },
    # High latency / timeout
    "high_latency": {
        "pattern": [
            "timeout",
            "high latency",
            "slow query",
            "deadline exceeded",
            "p99 spike",
        ],
        "category": "performance",
        "severity": "high",
        "suggestions": [
            {
                "action": "Scale horizontally",
                "description": "Add more instances to handle load.",
                "steps": [
                    "Check current replica count vs HPA max",
                    "Increase min/max replicas",
                    "Verify load balancing is working",
                ],
                "risk": "low",
                "effort": "low",
            },
            {
                "action": "Add caching layer",
                "description": "Reduce database load with caching.",
                "steps": [
                    "Identify frequently accessed data",
                    "Implement Redis/Memcached caching",
                    "Set appropriate TTLs",
                ],
                "risk": "medium",
                "effort": "medium",
            },
            {
                "action": "Optimize slow queries",
                "description": "Database queries may be the bottleneck.",
                "steps": [
                    "Enable query logging in Cloud SQL",
                    "Identify queries >100ms",
                    "Add indexes or rewrite queries",
                ],
                "risk": "medium",
                "effort": "high",
            },
        ],
    },
    # Error rate spike
    "error_spike": {
        "pattern": ["error rate", "5xx", "500 error", "internal server error"],
        "category": "errors",
        "severity": "high",
        "suggestions": [
            {
                "action": "Rollback recent deployment",
                "description": "If errors started after a deployment, rollback.",
                "steps": [
                    "Identify last successful revision",
                    "Rollback to previous version",
                    "Monitor error rate after rollback",
                ],
                "risk": "low",
                "effort": "low",
            },
            {
                "action": "Check downstream dependencies",
                "description": "Errors may be caused by failing dependencies.",
                "steps": [
                    "Review dependency health dashboards",
                    "Check for circuit breaker trips",
                    "Verify dependency SLOs",
                ],
                "risk": "low",
                "effort": "low",
            },
            {
                "action": "Add retry logic with backoff",
                "description": "Transient errors may be recoverable with retries.",
                "steps": [
                    "Implement exponential backoff",
                    "Add jitter to prevent thundering herd",
                    "Set reasonable retry limits",
                ],
                "risk": "low",
                "effort": "medium",
            },
        ],
    },
    # Cold starts
    "cold_start": {
        "pattern": ["cold start", "startup latency", "instance scaling"],
        "category": "serverless",
        "severity": "medium",
        "suggestions": [
            {
                "action": "Set minimum instances",
                "description": "Keep warm instances to avoid cold starts.",
                "steps": [
                    "Configure min-instances in Cloud Run",
                    "Balance cost vs latency requirements",
                    "Monitor instance count metrics",
                ],
                "risk": "low",
                "effort": "low",
            },
            {
                "action": "Optimize startup time",
                "description": "Reduce time to first request.",
                "steps": [
                    "Defer initialization of non-critical components",
                    "Use lazy loading for dependencies",
                    "Reduce container image size",
                ],
                "risk": "medium",
                "effort": "medium",
            },
        ],
    },
    # Pod scheduling issues
    "scheduling": {
        "pattern": ["pending pod", "insufficient", "unschedulable", "node affinity"],
        "category": "kubernetes",
        "severity": "high",
        "suggestions": [
            {
                "action": "Scale node pool",
                "description": "Not enough nodes to schedule pods.",
                "steps": [
                    "Check node pool autoscaling settings",
                    "Increase max nodes if needed",
                    "Verify quota is not exceeded",
                ],
                "risk": "low",
                "effort": "low",
            },
            {
                "action": "Reduce resource requests",
                "description": "Pods may be requesting more than needed.",
                "steps": [
                    "Review VPA recommendations",
                    "Reduce CPU/memory requests (not limits)",
                    "Monitor for performance impact",
                ],
                "risk": "medium",
                "effort": "low",
            },
        ],
    },
    # Pub/Sub backlog
    "pubsub_backlog": {
        "pattern": [
            "message backlog",
            "oldest unacked",
            "subscription lag",
            "dead letter",
        ],
        "category": "messaging",
        "severity": "medium",
        "suggestions": [
            {
                "action": "Scale subscribers",
                "description": "Add more subscriber instances to process backlog.",
                "steps": [
                    "Increase subscriber replica count",
                    "Verify subscriber is not CPU/memory bound",
                    "Monitor messages/second per subscriber",
                ],
                "risk": "low",
                "effort": "low",
            },
            {
                "action": "Increase ack deadline",
                "description": "Messages may be timing out before processing completes.",
                "steps": [
                    "Review current ack deadline setting",
                    "Increase to match 95th percentile processing time",
                    "Implement deadline extension for long operations",
                ],
                "risk": "low",
                "effort": "low",
            },
            {
                "action": "Investigate dead letter queue",
                "description": "Messages are failing repeatedly.",
                "steps": [
                    "Enable dead letter topic if not configured",
                    "Analyze messages in DLQ for patterns",
                    "Fix processing bugs and replay messages",
                ],
                "risk": "medium",
                "effort": "medium",
            },
        ],
    },
    # Disk pressure
    "disk_pressure": {
        "pattern": ["disk pressure", "storage full", "ephemeral storage", "no space"],
        "category": "storage",
        "severity": "high",
        "suggestions": [
            {
                "action": "Clean up logs and temp files",
                "description": "Remove unnecessary files consuming disk space.",
                "steps": [
                    "Check log rotation configuration",
                    "Clean /tmp and cache directories",
                    "Review persistent volume usage",
                ],
                "risk": "low",
                "effort": "low",
            },
            {
                "action": "Increase storage allocation",
                "description": "Resize persistent volumes or ephemeral storage.",
                "steps": [
                    "Expand PVC (if supported by storage class)",
                    "Increase ephemeral storage in pod spec",
                    "Consider using a larger machine type",
                ],
                "risk": "medium",
                "effort": "medium",
            },
        ],
    },
}


@adk_tool
def generate_remediation_suggestions(
    finding_summary: str,
    finding_details: dict | None = None,
) -> str:
    """
    Generate remediation suggestions based on investigation findings.

    Takes the summary of what was found during analysis and returns
    actionable remediation steps ranked by effectiveness and risk.

    Args:
        finding_summary: Text description of the issue found.
        finding_details: Optional structured details (severity, affected services, etc.)

    Returns:
        JSON with prioritized remediation suggestions.

    Example:
        generate_remediation_suggestions(
            "Container frontend-pod is repeatedly OOMKilled",
            {"severity": "high", "service": "frontend"}
        )
    """
    try:
        summary_lower = finding_summary.lower()

        matched_patterns = []
        for pattern_name, pattern_data in REMEDIATION_PATTERNS.items():
            for keyword in pattern_data["pattern"]:
                if keyword.lower() in summary_lower:
                    matched_patterns.append((pattern_name, pattern_data))
                    break

        if not matched_patterns:
            # Generic suggestions if no pattern matched
            return json.dumps(
                {
                    "matched_patterns": [],
                    "suggestions": [
                        {
                            "action": "Enable detailed logging",
                            "description": "Increase log verbosity to gather more diagnostic information.",
                            "steps": [
                                "Set log level to DEBUG",
                                "Reproduce the issue",
                                "Analyze detailed logs",
                            ],
                            "risk": "low",
                            "effort": "low",
                        },
                        {
                            "action": "Create a minimal reproduction",
                            "description": "Isolate the issue to identify root cause.",
                            "steps": [
                                "Identify affected component",
                                "Create test case that reproduces issue",
                                "Systematically eliminate variables",
                            ],
                            "risk": "low",
                            "effort": "medium",
                        },
                    ],
                    "note": "No specific pattern matched. Please provide more details about the issue.",
                },
                indent=2,
            )

        # Collect all suggestions from matched patterns
        all_suggestions = []
        categories = set()

        for pattern_name, pattern_data in matched_patterns:
            categories.add(pattern_data["category"])
            for suggestion in pattern_data["suggestions"]:
                suggestion_copy = dict(suggestion)
                suggestion_copy["source_pattern"] = pattern_name
                suggestion_copy["category"] = pattern_data["category"]
                all_suggestions.append(suggestion_copy)

        # Sort by risk (low first) and effort (low first)
        risk_order = {"low": 0, "medium": 1, "high": 2}
        effort_order = {"low": 0, "medium": 1, "high": 2}

        all_suggestions.sort(
            key=lambda x: (
                risk_order.get(x.get("risk", "medium"), 1),
                effort_order.get(x.get("effort", "medium"), 1),
            )
        )

        result = {
            "matched_patterns": [p[0] for p in matched_patterns],
            "categories": list(categories),
            "finding_summary": finding_summary,
            "suggestions": all_suggestions,
            "recommended_first_action": all_suggestions[0] if all_suggestions else None,
            "quick_wins": [
                s
                for s in all_suggestions
                if s.get("risk") == "low" and s.get("effort") == "low"
            ],
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Failed to generate remediation suggestions: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def get_gcloud_commands(
    remediation_type: str,
    resource_name: str,
    project_id: str,
    region: str | None = None,
    **kwargs: Any,
) -> str:
    """
    Generate ready-to-run gcloud commands for common remediations.

    When you know what fix is needed, this generates the exact commands
    to execute. Copy-paste SRE!

    Args:
        remediation_type: Type of remediation (scale_up, rollback, increase_memory, etc.)
        resource_name: Name of the resource to modify.
        project_id: Google Cloud project ID.
        region: Optional region for regional resources.
        **kwargs: Additional parameters specific to remediation type.

    Returns:
        JSON with gcloud commands and explanations.

    Example:
        get_gcloud_commands("scale_up", "frontend-service", "my-project", region="us-central1", replicas=5)
    """
    try:
        commands = []

        if remediation_type == "scale_up":
            replicas = kwargs.get("replicas", 3)
            commands = [
                {
                    "description": f"Scale Cloud Run service to {replicas} min instances",
                    "command": f"gcloud run services update {resource_name} --min-instances={replicas} --region={region} --project={project_id}",
                },
                {
                    "description": "Verify the update",
                    "command": f"gcloud run services describe {resource_name} --region={region} --project={project_id} --format='value(spec.template.spec.containerConcurrency)'",
                },
            ]

        elif remediation_type == "rollback":
            revision = kwargs.get("revision", "PREVIOUS")
            commands = [
                {
                    "description": "List recent revisions",
                    "command": f"gcloud run revisions list --service={resource_name} --region={region} --project={project_id}",
                },
                {
                    "description": "Rollback to previous revision",
                    "command": f"gcloud run services update-traffic {resource_name} --to-revisions={revision}=100 --region={region} --project={project_id}",
                },
            ]

        elif remediation_type == "increase_memory":
            memory = kwargs.get("memory", "1Gi")
            commands = [
                {
                    "description": f"Update memory limit to {memory}",
                    "command": f"gcloud run services update {resource_name} --memory={memory} --region={region} --project={project_id}",
                },
            ]

        elif remediation_type == "scale_gke_nodepool":
            cluster = kwargs.get("cluster")
            nodepool = kwargs.get("nodepool", "default-pool")
            min_nodes = kwargs.get("min_nodes", 3)
            max_nodes = kwargs.get("max_nodes", 10)
            zone = kwargs.get("zone", region)
            commands = [
                {
                    "description": f"Update node pool autoscaling to {min_nodes}-{max_nodes} nodes",
                    "command": f"gcloud container clusters update {cluster} --node-pool={nodepool} --enable-autoscaling --min-nodes={min_nodes} --max-nodes={max_nodes} --zone={zone} --project={project_id}",
                },
            ]

        elif remediation_type == "increase_sql_connections":
            max_connections = kwargs.get("max_connections", 100)
            commands = [
                {
                    "description": f"Increase Cloud SQL max connections to {max_connections}",
                    "command": f"gcloud sql instances patch {resource_name} --database-flags=max_connections={max_connections} --project={project_id}",
                },
                {
                    "description": "Note: This will restart the instance",
                    "command": "# Instance restart required for flag changes",
                },
            ]

        elif remediation_type == "enable_min_instances":
            min_instances = kwargs.get("min_instances", 1)
            commands = [
                {
                    "description": f"Set minimum instances to {min_instances} to avoid cold starts",
                    "command": f"gcloud run services update {resource_name} --min-instances={min_instances} --region={region} --project={project_id}",
                },
            ]

        elif remediation_type == "update_hpa":
            namespace = kwargs.get("namespace", "default")
            min_replicas = kwargs.get("min_replicas", 3)
            max_replicas = kwargs.get("max_replicas", 10)
            commands = [
                {
                    "description": "Update HPA with kubectl (requires cluster credentials)",
                    "command": f'kubectl patch hpa {resource_name} -n {namespace} -p \'{{"spec":{{"minReplicas":{min_replicas},"maxReplicas":{max_replicas}}}}}\'',
                },
            ]

        else:
            return json.dumps(
                {
                    "error": f"Unknown remediation type: {remediation_type}",
                    "available_types": [
                        "scale_up",
                        "rollback",
                        "increase_memory",
                        "scale_gke_nodepool",
                        "increase_sql_connections",
                        "enable_min_instances",
                        "update_hpa",
                    ],
                }
            )

        result = {
            "remediation_type": remediation_type,
            "resource": resource_name,
            "project": project_id,
            "commands": commands,
            "warning": "Review commands before executing. Some changes may cause brief service interruption.",
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Failed to generate gcloud commands: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def estimate_remediation_risk(
    action: str,
    service_name: str,
    change_description: str,
) -> str:
    """
    Estimate the risk level of a proposed remediation action.

    Not all fixes are created equal - some are safe to try immediately,
    others need careful planning. This helps prioritize.

    Args:
        action: The remediation action being considered.
        service_name: Name of the affected service.
        change_description: Description of what will change.

    Returns:
        JSON with risk assessment, potential impacts, and recommendations.

    Example:
        estimate_remediation_risk(
            "rollback",
            "checkout-service",
            "Rollback from v2.3.1 to v2.3.0"
        )
    """
    try:
        action_lower = action.lower()

        # Risk levels for different action types
        low_risk_actions = [
            "scale up",
            "increase replicas",
            "add instances",
            "increase memory",
            "increase cpu",
            "enable logging",
            "add monitoring",
        ]
        medium_risk_actions = [
            "rollback",
            "scale down",
            "modify config",
            "update timeout",
            "change pool size",
            "restart",
            "redeploy",
        ]
        high_risk_actions = [
            "delete",
            "remove",
            "disable",
            "migration",
            "schema change",
            "database migration",
            "breaking change",
        ]

        risk_level = "medium"  # default
        risk_factors = []
        mitigations = []

        for keyword in low_risk_actions:
            if keyword in action_lower:
                risk_level = "low"
                break

        for keyword in medium_risk_actions:
            if keyword in action_lower:
                risk_level = "medium"
                break

        for keyword in high_risk_actions:
            if keyword in action_lower:
                risk_level = "high"
                break

        # Analyze risk factors
        if "database" in action_lower or "sql" in action_lower:
            risk_factors.append("Database changes can affect data integrity")
            mitigations.append("Take a backup before proceeding")

        if "rollback" in action_lower:
            risk_factors.append(
                "Rollback may lose features or data written by newer version"
            )
            mitigations.append("Verify backward compatibility of data")

        if "restart" in action_lower:
            risk_factors.append("Restart will cause brief service interruption")
            mitigations.append("Schedule during low-traffic window if possible")

        if "config" in action_lower:
            risk_factors.append("Configuration changes may have unexpected effects")
            mitigations.append("Test in staging environment first")

        if "scale down" in action_lower:
            risk_factors.append("Reducing capacity may impact performance under load")
            mitigations.append("Monitor closely after change")

        # Add general mitigations
        mitigations.extend(
            [
                "Have a rollback plan ready",
                "Monitor error rates during and after change",
                "Communicate change to relevant stakeholders",
            ]
        )

        result = {
            "action": action,
            "service": service_name,
            "change": change_description,
            "risk_assessment": {
                "level": risk_level,
                "confidence": "medium",
                "factors": risk_factors
                if risk_factors
                else ["No specific risk factors identified"],
            },
            "recommendations": {
                "proceed": risk_level != "high",
                "require_approval": risk_level == "high",
                "mitigations": mitigations,
            },
            "checklist": [
                f"[ ] Review change: {change_description}",
                "[ ] Backup critical data if applicable",
                "[ ] Notify on-call if outside business hours",
                "[ ] Prepare rollback procedure",
                "[ ] Execute change",
                "[ ] Monitor for 15 minutes post-change",
                "[ ] Document outcome",
            ],
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Failed to estimate remediation risk: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@adk_tool
def find_similar_past_incidents(
    error_pattern: str,
    service_name: str | None = None,
    days_back: int = 90,
) -> str:
    """
    Search for similar past incidents to learn from previous resolutions.

    Those who don't learn from history are doomed to repeat it!
    Check if this problem has been solved before.

    Args:
        error_pattern: The error pattern or symptom to search for.
        service_name: Optional service name to narrow search.
        days_back: How far back to search (default 90 days).

    Returns:
        JSON with similar incidents and their resolutions (from knowledge base).

    Note: This currently uses a static knowledge base. In production,
    this would integrate with incident management systems like PagerDuty,
    OpsGenie, or internal postmortem databases.

    Example:
        find_similar_past_incidents("OOMKilled", "frontend-service", 30)
    """
    try:
        pattern_lower = error_pattern.lower()

        # Static knowledge base (in production, this would query an incident database)
        known_incidents = [
            {
                "pattern": "oom",
                "title": "Frontend OOMKilled during peak traffic",
                "date": "2024-01-15",
                "service": "frontend",
                "root_cause": "Memory leak in image processing library",
                "resolution": "Updated library version and increased memory limits",
                "ttd_minutes": 15,
                "ttr_minutes": 45,
                "prevention": "Added memory usage alerting at 80% threshold",
            },
            {
                "pattern": "connection pool",
                "title": "Database connection exhaustion",
                "date": "2024-02-20",
                "service": "api-gateway",
                "root_cause": "Connection leak in error handling path",
                "resolution": "Fixed try-finally block and increased pool size",
                "ttd_minutes": 30,
                "ttr_minutes": 60,
                "prevention": "Added connection pool metrics and alerting",
            },
            {
                "pattern": "timeout",
                "title": "Checkout timeout during flash sale",
                "date": "2024-03-10",
                "service": "checkout",
                "root_cause": "Inventory service overloaded",
                "resolution": "Added caching layer and increased replicas",
                "ttd_minutes": 10,
                "ttr_minutes": 30,
                "prevention": "Implemented load shedding and circuit breaker",
            },
            {
                "pattern": "cold start",
                "title": "High latency after deployment",
                "date": "2024-03-25",
                "service": "api",
                "root_cause": "Cloud Run scaling from zero",
                "resolution": "Set min-instances=2 for production",
                "ttd_minutes": 5,
                "ttr_minutes": 10,
                "prevention": "Always set min-instances for latency-sensitive services",
            },
            {
                "pattern": "5xx",
                "title": "500 errors after deployment",
                "date": "2024-04-01",
                "service": "payment",
                "root_cause": "Missing environment variable in new deployment",
                "resolution": "Rolled back and fixed deployment config",
                "ttd_minutes": 5,
                "ttr_minutes": 15,
                "prevention": "Added config validation in CI/CD pipeline",
            },
        ]

        # Find matching incidents
        matches = []
        for incident in known_incidents:
            if (
                str(incident["pattern"]) in pattern_lower
                or pattern_lower in str(incident["pattern"])
            ):
                if (
                    service_name is None
                    or service_name.lower() in str(incident["service"]).lower()
                ):
                    matches.append(incident)

        if not matches:
            # Partial matching
            for incident in known_incidents:
                for word in pattern_lower.split():
                    if (
                        word in str(incident["title"]).lower()
                        or word in str(incident["root_cause"]).lower()
                    ):
                        if incident not in matches:
                            matches.append(incident)

        result = {
            "search_pattern": error_pattern,
            "service_filter": service_name,
            "search_window_days": days_back,
            "matches_found": len(matches),
            "similar_incidents": matches,
        }

        if matches:
            # Summarize learnings
            key_learnings = []
            for inc in matches:
                key_learnings.append(
                    {
                        "incident": inc["title"],
                        "lesson": inc.get("prevention", inc["resolution"]),
                    }
                )
            result["key_learnings"] = key_learnings

        else:
            result["note"] = (
                "No similar incidents found in knowledge base. "
                "Consider documenting this incident for future reference."
            )

        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Failed to find similar incidents: {e!s}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
