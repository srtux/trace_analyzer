"""Log analysis tools for SRE Agent.

This module provides advanced log analysis capabilities:
- Log pattern extraction using Drain3
- Pattern comparison between time ranges
- Anomaly detection for emergent log patterns
- Smart payload extraction from various log formats

Tools:
    - extract_log_patterns: Extract log templates using Drain3
    - compare_log_patterns: Compare patterns between time periods
    - analyze_log_anomalies: Find anomalous/emergent patterns
    - extract_log_message: Smart extraction of message from payloads
"""

from .extraction import (
    LogMessageExtractor,
    extract_log_message,
    extract_messages_from_entries,
)
from .patterns import (
    LogPatternExtractor,
    analyze_log_anomalies,
    compare_log_patterns,
    extract_log_patterns,
    get_pattern_summary,
)

__all__ = [
    "LogMessageExtractor",
    "LogPatternExtractor",
    "analyze_log_anomalies",
    "compare_log_patterns",
    "extract_log_message",
    "extract_log_patterns",
    "extract_messages_from_entries",
    "get_pattern_summary",
]
