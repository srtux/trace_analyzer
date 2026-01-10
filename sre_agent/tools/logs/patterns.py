"""Log pattern extraction using Drain3 algorithm.

This module provides log template extraction and pattern analysis using
the Drain3 algorithm, which efficiently clusters logs into patterns.

The main goals are:
1. Compress repetitive logs into patterns
2. Compare patterns between time ranges to find anomalies
3. Identify newly emergent patterns that may indicate issues
4. Present distilled information to avoid LLM context overflow
"""

import hashlib
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

from ..common import adk_tool
from .extraction import extract_log_message

logger = logging.getLogger(__name__)


@dataclass
class LogPattern:
    """Represents a discovered log pattern/template."""

    pattern_id: str
    template: str
    count: int
    first_seen: str | None = None
    last_seen: str | None = None
    severity_counts: dict[str, int] = field(default_factory=dict)
    sample_messages: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "template": self.template,
            "count": self.count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "severity_counts": self.severity_counts,
            "sample_messages": self.sample_messages[:3],  # Limit samples
            "resources": list(set(self.resources))[:5],  # Unique, limited
        }


@dataclass
class PatternComparison:
    """Comparison result between two time periods."""

    new_patterns: list[LogPattern]  # Patterns only in period 2
    disappeared_patterns: list[LogPattern]  # Patterns only in period 1
    increased_patterns: list[tuple[LogPattern, float]]  # Pattern, % increase
    decreased_patterns: list[tuple[LogPattern, float]]  # Pattern, % decrease
    stable_patterns: list[LogPattern]

    def to_dict(self) -> dict[str, Any]:
        return {
            "new_patterns": [p.to_dict() for p in self.new_patterns],
            "disappeared_patterns": [p.to_dict() for p in self.disappeared_patterns],
            "increased_patterns": [
                {"pattern": p.to_dict(), "increase_pct": pct}
                for p, pct in self.increased_patterns
            ],
            "decreased_patterns": [
                {"pattern": p.to_dict(), "decrease_pct": pct}
                for p, pct in self.decreased_patterns
            ],
            "stable_patterns_count": len(self.stable_patterns),
        }


class LogPatternExtractor:
    """
    Extracts log patterns using Drain3 algorithm.

    Drain3 is a streaming log parser that efficiently extracts templates
    from unstructured log messages. It's designed to handle high volumes
    of logs without requiring training data.

    Key features:
    - Streaming: Can process logs one at a time
    - Fast: O(1) per log message after warmup
    - Accurate: Good at detecting variable parts
    """

    def __init__(
        self,
        depth: int = 4,
        sim_th: float = 0.4,
        max_children: int = 100,
        max_clusters: int = 1000,
    ):
        """
        Initialize the pattern extractor.

        Args:
            depth: Depth of the parse tree (higher = more patterns)
            sim_th: Similarity threshold for clustering (0-1)
            max_children: Max children per node
            max_clusters: Maximum number of patterns to track
        """
        config = TemplateMinerConfig()
        config.drain_depth = depth
        config.drain_sim_th = sim_th
        config.drain_max_children = max_children
        config.drain_max_clusters = max_clusters

        # Mask common variable patterns
        config.masking_instructions = [
            {"regex_pattern": r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "mask_with": "<TIMESTAMP>"},
            {"regex_pattern": r"\b\d{4}-\d{2}-\d{2}", "mask_with": "<DATE>"},
            {"regex_pattern": r"\b\d{2}:\d{2}:\d{2}", "mask_with": "<TIME>"},
            {"regex_pattern": r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "mask_with": "<UUID>"},
            {"regex_pattern": r"\b[0-9a-f]{24,}\b", "mask_with": "<ID>"},
            {"regex_pattern": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "mask_with": "<IP>"},
            {"regex_pattern": r"\b\d+\.\d+ms\b", "mask_with": "<DURATION>"},
            {"regex_pattern": r"\b\d+ms\b", "mask_with": "<DURATION>"},
            {"regex_pattern": r'"\w+@\w+\.\w+"', "mask_with": "<EMAIL>"},
        ]

        self.miner = TemplateMiner(config=config)
        self.patterns: dict[str, LogPattern] = {}
        self._cluster_to_pattern: dict[int, str] = {}

    def add_log(
        self,
        message: str,
        timestamp: str | None = None,
        severity: str | None = None,
        resource: str | None = None,
    ) -> str:
        """
        Add a log message and return its pattern ID.

        Args:
            message: The log message to process
            timestamp: Optional timestamp for tracking
            severity: Optional severity level
            resource: Optional resource type

        Returns:
            The pattern ID this message belongs to
        """
        result = self.miner.add_log_message(message)

        if result is None:
            return "unknown"

        cluster_id = result.cluster_id
        template = result.get_template()

        # Generate stable pattern ID from template
        pattern_id = self._generate_pattern_id(template)

        # Map cluster to pattern
        self._cluster_to_pattern[cluster_id] = pattern_id

        # Update or create pattern
        if pattern_id not in self.patterns:
            self.patterns[pattern_id] = LogPattern(
                pattern_id=pattern_id,
                template=template,
                count=0,
                first_seen=timestamp,
                severity_counts={},
                sample_messages=[],
                resources=[],
            )

        pattern = self.patterns[pattern_id]
        pattern.count += 1
        pattern.last_seen = timestamp

        if severity:
            pattern.severity_counts[severity] = pattern.severity_counts.get(severity, 0) + 1

        if resource:
            pattern.resources.append(resource)

        # Keep limited samples
        if len(pattern.sample_messages) < 5:
            pattern.sample_messages.append(message[:200])

        return pattern_id

    def _generate_pattern_id(self, template: str) -> str:
        """Generate a stable pattern ID from template."""
        # Use hash of template for consistent IDs
        return hashlib.md5(template.encode()).hexdigest()[:8]

    def get_patterns(
        self,
        min_count: int = 1,
        sort_by: str = "count",
        limit: int | None = None,
    ) -> list[LogPattern]:
        """
        Get extracted patterns.

        Args:
            min_count: Minimum occurrence count to include
            sort_by: Sort by "count", "severity", or "recent"
            limit: Maximum patterns to return

        Returns:
            List of LogPattern objects
        """
        patterns = [p for p in self.patterns.values() if p.count >= min_count]

        if sort_by == "count":
            patterns.sort(key=lambda p: p.count, reverse=True)
        elif sort_by == "severity":
            # Sort by error/warning count
            def severity_score(p: LogPattern) -> int:
                return (
                    p.severity_counts.get("ERROR", 0) * 10
                    + p.severity_counts.get("CRITICAL", 0) * 20
                    + p.severity_counts.get("WARNING", 0) * 5
                )
            patterns.sort(key=severity_score, reverse=True)
        elif sort_by == "recent":
            patterns.sort(key=lambda p: p.last_seen or "", reverse=True)

        if limit:
            patterns = patterns[:limit]

        return patterns

    def get_summary(self, max_patterns: int = 20) -> dict[str, Any]:
        """
        Get a compact summary suitable for LLM context.

        This method is designed to avoid context window overflow by
        providing distilled, actionable information.

        Args:
            max_patterns: Maximum number of patterns to include

        Returns:
            A summary dict with key metrics and top patterns
        """
        total_logs = sum(p.count for p in self.patterns.values())
        total_patterns = len(self.patterns)

        # Get severity distribution
        severity_totals: dict[str, int] = {}
        for pattern in self.patterns.values():
            for sev, count in pattern.severity_counts.items():
                severity_totals[sev] = severity_totals.get(sev, 0) + count

        # Get top patterns by count
        top_patterns = self.get_patterns(min_count=1, sort_by="count", limit=max_patterns)

        # Get error patterns
        error_patterns = [
            p for p in self.patterns.values()
            if p.severity_counts.get("ERROR", 0) > 0
            or p.severity_counts.get("CRITICAL", 0) > 0
        ]
        error_patterns.sort(key=lambda p: p.severity_counts.get("ERROR", 0), reverse=True)

        return {
            "total_logs_processed": total_logs,
            "unique_patterns": total_patterns,
            "severity_distribution": severity_totals,
            "compression_ratio": round(total_logs / max(total_patterns, 1), 2),
            "top_patterns": [p.to_dict() for p in top_patterns],
            "error_patterns": [p.to_dict() for p in error_patterns[:10]],
        }


def compare_patterns(
    patterns1: list[LogPattern],
    patterns2: list[LogPattern],
    significance_threshold: float = 0.5,
) -> PatternComparison:
    """
    Compare patterns between two time periods.

    This function identifies:
    - New patterns (only in period 2) - potential new issues
    - Disappeared patterns (only in period 1)
    - Significantly increased patterns
    - Significantly decreased patterns

    Args:
        patterns1: Patterns from baseline period
        patterns2: Patterns from comparison period
        significance_threshold: Minimum % change to be significant

    Returns:
        PatternComparison with categorized patterns
    """
    # Create lookup by template
    p1_by_id = {p.pattern_id: p for p in patterns1}
    p2_by_id = {p.pattern_id: p for p in patterns2}

    # Calculate totals for normalization
    total1 = sum(p.count for p in patterns1) or 1
    total2 = sum(p.count for p in patterns2) or 1

    new_patterns = []
    disappeared_patterns = []
    increased_patterns = []
    decreased_patterns = []
    stable_patterns = []

    # Find new patterns
    for pid, pattern in p2_by_id.items():
        if pid not in p1_by_id:
            new_patterns.append(pattern)

    # Find disappeared patterns
    for pid, pattern in p1_by_id.items():
        if pid not in p2_by_id:
            disappeared_patterns.append(pattern)

    # Compare common patterns
    for pid in set(p1_by_id.keys()) & set(p2_by_id.keys()):
        p1 = p1_by_id[pid]
        p2 = p2_by_id[pid]

        # Normalize by total
        rate1 = p1.count / total1
        rate2 = p2.count / total2

        if rate1 > 0:
            change_pct = (rate2 - rate1) / rate1
        else:
            change_pct = 1.0 if rate2 > 0 else 0.0

        if change_pct > significance_threshold:
            increased_patterns.append((p2, round(change_pct * 100, 1)))
        elif change_pct < -significance_threshold:
            decreased_patterns.append((p2, round(abs(change_pct) * 100, 1)))
        else:
            stable_patterns.append(p2)

    # Sort by significance
    new_patterns.sort(key=lambda p: p.count, reverse=True)
    increased_patterns.sort(key=lambda x: x[1], reverse=True)
    decreased_patterns.sort(key=lambda x: x[1], reverse=True)

    return PatternComparison(
        new_patterns=new_patterns,
        disappeared_patterns=disappeared_patterns,
        increased_patterns=increased_patterns,
        decreased_patterns=decreased_patterns,
        stable_patterns=stable_patterns,
    )


@adk_tool
def extract_log_patterns(
    log_entries: list[dict[str, Any]],
    max_patterns: int = 30,
    min_count: int = 2,
) -> dict[str, Any]:
    """
    Extract log patterns from a list of log entries using Drain3.

    This tool compresses repetitive logs into patterns, making it easier
    to understand the log landscape without overwhelming context.

    Args:
        log_entries: List of log entry dicts (from list_log_entries)
        max_patterns: Maximum patterns to return
        min_count: Minimum occurrences for a pattern

    Returns:
        Summary dict with patterns and statistics
    """
    extractor = LogPatternExtractor()

    for entry in log_entries:
        message = extract_log_message(entry)
        timestamp = entry.get("timestamp", "")
        severity = entry.get("severity", "")
        resource = entry.get("resource", {})
        resource_type = resource.get("type", "") if isinstance(resource, dict) else ""

        extractor.add_log(
            message=message,
            timestamp=timestamp,
            severity=severity,
            resource=resource_type,
        )

    return extractor.get_summary(max_patterns=max_patterns)


@adk_tool
def compare_log_patterns(
    baseline_entries: list[dict[str, Any]],
    comparison_entries: list[dict[str, Any]],
    significance_threshold: float = 0.5,
) -> dict[str, Any]:
    """
    Compare log patterns between two time periods to find anomalies.

    This is the key tool for detecting emergent issues. It identifies:
    - NEW patterns: Logs that didn't exist before (potential new bugs!)
    - DISAPPEARED patterns: Issues that may have been resolved
    - INCREASED patterns: Errors happening more frequently
    - DECREASED patterns: Improvements

    Args:
        baseline_entries: Log entries from the baseline period
        comparison_entries: Log entries from the period to compare
        significance_threshold: Minimum % change to be significant (0.5 = 50%)

    Returns:
        Comparison results with categorized patterns
    """
    # Extract patterns from both periods
    baseline_extractor = LogPatternExtractor()
    comparison_extractor = LogPatternExtractor()

    for entry in baseline_entries:
        message = extract_log_message(entry)
        baseline_extractor.add_log(
            message=message,
            timestamp=entry.get("timestamp", ""),
            severity=entry.get("severity", ""),
        )

    for entry in comparison_entries:
        message = extract_log_message(entry)
        comparison_extractor.add_log(
            message=message,
            timestamp=entry.get("timestamp", ""),
            severity=entry.get("severity", ""),
        )

    baseline_patterns = baseline_extractor.get_patterns()
    comparison_patterns = comparison_extractor.get_patterns()

    comparison = compare_patterns(
        baseline_patterns,
        comparison_patterns,
        significance_threshold=significance_threshold,
    )

    return {
        "baseline_summary": {
            "total_logs": sum(p.count for p in baseline_patterns),
            "unique_patterns": len(baseline_patterns),
        },
        "comparison_summary": {
            "total_logs": sum(p.count for p in comparison_patterns),
            "unique_patterns": len(comparison_patterns),
        },
        "anomalies": comparison.to_dict(),
        "alert_level": _determine_alert_level(comparison),
    }


@adk_tool
def analyze_log_anomalies(
    log_entries: list[dict[str, Any]],
    focus_on_errors: bool = True,
    max_results: int = 10,
) -> dict[str, Any]:
    """
    Analyze logs for anomalous patterns, focusing on errors if specified.

    This tool extracts patterns and highlights the most concerning ones,
    perfect for quick incident triage.

    Args:
        log_entries: List of log entry dicts
        focus_on_errors: If True, prioritize ERROR/CRITICAL patterns
        max_results: Maximum patterns to return

    Returns:
        Analysis results with prioritized anomalies
    """
    extractor = LogPatternExtractor()

    for entry in log_entries:
        message = extract_log_message(entry)
        extractor.add_log(
            message=message,
            timestamp=entry.get("timestamp", ""),
            severity=entry.get("severity", ""),
            resource=entry.get("resource", {}).get("type", "")
            if isinstance(entry.get("resource"), dict) else "",
        )

    # Get patterns sorted appropriately
    sort_by = "severity" if focus_on_errors else "count"
    patterns = extractor.get_patterns(sort_by=sort_by, limit=max_results)

    # Categorize by severity
    critical = [p for p in patterns if p.severity_counts.get("CRITICAL", 0) > 0]
    errors = [p for p in patterns if p.severity_counts.get("ERROR", 0) > 0]
    warnings = [p for p in patterns if p.severity_counts.get("WARNING", 0) > 0]

    return {
        "total_logs": sum(p.count for p in extractor.patterns.values()),
        "unique_patterns": len(extractor.patterns),
        "critical_patterns": [p.to_dict() for p in critical[:5]],
        "error_patterns": [p.to_dict() for p in errors[:5]],
        "warning_patterns": [p.to_dict() for p in warnings[:5]],
        "top_patterns": [p.to_dict() for p in patterns],
        "recommendation": _generate_recommendation(critical, errors, warnings),
    }


def get_pattern_summary(
    patterns: list[LogPattern],
    max_length: int = 2000,
) -> str:
    """
    Generate a compact text summary of patterns for LLM context.

    This is carefully designed to provide maximum insight with minimum
    tokens, avoiding context window overflow.

    Args:
        patterns: List of LogPattern objects
        max_length: Maximum characters in output

    Returns:
        A compact, human-readable summary
    """
    if not patterns:
        return "No patterns found."

    lines = [f"📊 {len(patterns)} unique patterns found:\n"]
    current_length = len(lines[0])

    for i, p in enumerate(patterns, 1):
        # Create compact pattern line
        severity_info = ""
        if p.severity_counts:
            top_sev = max(p.severity_counts.items(), key=lambda x: x[1])
            severity_info = f" [{top_sev[0]}:{top_sev[1]}]"

        line = f"{i}. ({p.count}x){severity_info} {p.template[:100]}...\n"

        if current_length + len(line) > max_length:
            lines.append(f"... and {len(patterns) - i + 1} more patterns")
            break

        lines.append(line)
        current_length += len(line)

    return "".join(lines)


def _determine_alert_level(comparison: PatternComparison) -> str:
    """Determine alert level based on comparison results."""
    # Check for critical new patterns
    new_error_patterns = [
        p for p in comparison.new_patterns
        if p.severity_counts.get("ERROR", 0) > 0
        or p.severity_counts.get("CRITICAL", 0) > 0
    ]

    if new_error_patterns:
        return "🔴 HIGH - New error patterns detected!"

    if comparison.new_patterns and len(comparison.new_patterns) > 5:
        return "🟠 MEDIUM - Multiple new patterns detected"

    if comparison.increased_patterns:
        high_increase = [p for p, pct in comparison.increased_patterns if pct > 200]
        if high_increase:
            return "🟠 MEDIUM - Significant increase in some patterns"

    return "🟢 LOW - No significant anomalies"


def _generate_recommendation(
    critical: list[LogPattern],
    errors: list[LogPattern],
    warnings: list[LogPattern],
) -> str:
    """Generate actionable recommendations."""
    if critical:
        return (
            f"🚨 CRITICAL: Found {len(critical)} critical patterns! "
            f"Top pattern: '{critical[0].template[:80]}...' "
            f"occurred {critical[0].count} times. Investigate immediately!"
        )

    if errors:
        return (
            f"⚠️ ERRORS: Found {len(errors)} error patterns. "
            f"Most frequent: '{errors[0].template[:80]}...' "
            f"({errors[0].count} occurrences). Check error handling."
        )

    if warnings:
        return (
            f"📝 WARNINGS: {len(warnings)} warning patterns detected. "
            "Consider reviewing for potential issues."
        )

    return "✅ Logs look healthy! No critical issues detected."
