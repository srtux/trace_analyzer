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

from .patterns import (
    LogPatternExtractor,
    extract_log_patterns,
    compare_log_patterns,
    analyze_log_anomalies,
    get_pattern_summary,
)
from .extraction import (
    extract_log_message,
    extract_messages_from_entries,
    LogMessageExtractor,
)

__all__ = [
    "LogPatternExtractor",
    "extract_log_patterns",
    "compare_log_patterns",
    "analyze_log_anomalies",
    "get_pattern_summary",
    "extract_log_message",
    "extract_messages_from_entries",
    "LogMessageExtractor",
]
