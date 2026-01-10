"""Remediation suggestion and recommendation tools.

This module provides automated suggestions for common issues found during
SRE analysis. Think of it as having a senior SRE's experience encoded
into actionable recommendations.
"""

from .suggestions import (
    estimate_remediation_risk,
    find_similar_past_incidents,
    generate_remediation_suggestions,
    get_gcloud_commands,
)

__all__ = [
    "estimate_remediation_risk",
    "find_similar_past_incidents",
    "generate_remediation_suggestions",
    "get_gcloud_commands",
]
