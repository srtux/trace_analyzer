"""Smart log message extraction from various payload formats.

This module handles extracting the actual log message from Cloud Logging
entries, which can use either textPayload or jsonPayload formats.

For jsonPayload, we use heuristics to find the main message field:
1. Common field names: message, msg, log, text, body, error, description
2. Longest string field (often the log message)
3. Field containing common log patterns
"""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Common message field names in order of priority
MESSAGE_FIELD_NAMES = [
    "message",
    "msg",
    "log",
    "text",
    "body",
    "error",
    "error_message",
    "errorMessage",
    "description",
    "content",
    "data",
    "payload",
    "event",
    "detail",
    "details",
    "reason",
    "summary",
    "info",
]

# Patterns that indicate a field is likely the log message
LOG_MESSAGE_PATTERNS = [
    r"\d{4}-\d{2}-\d{2}",  # Date pattern
    r"\d{2}:\d{2}:\d{2}",  # Time pattern
    r"\[(?:INFO|WARN|ERROR|DEBUG|TRACE)\]",  # Log level
    r"(?:Exception|Error|Failed|Success|Started|Completed)",  # Common log words
    r"(?:GET|POST|PUT|DELETE|PATCH)\s+/",  # HTTP methods
]


class LogMessageExtractor:
    """
    Intelligent extractor for log messages from various payload formats.

    Handles:
    - textPayload: Direct string extraction
    - jsonPayload: Heuristic-based field detection
    - protoPayload: Audit log extraction
    """

    def __init__(self):
        self._field_cache: dict[str, str] = {}
        self._pattern_re = [re.compile(p, re.IGNORECASE) for p in LOG_MESSAGE_PATTERNS]

    def extract(self, log_entry: dict[str, Any]) -> str:
        """
        Extract the log message from a Cloud Logging entry.

        Args:
            log_entry: A log entry dict with payload field

        Returns:
            The extracted log message string
        """
        # Try textPayload first (simplest case)
        if "textPayload" in log_entry:
            text = log_entry["textPayload"]
            if isinstance(text, str):
                return text.strip()

        # Try jsonPayload
        if "jsonPayload" in log_entry:
            return self._extract_from_json(log_entry["jsonPayload"])

        # Try protoPayload (audit logs)
        if "protoPayload" in log_entry:
            return self._extract_from_proto(log_entry["protoPayload"])

        # Fallback: try common payload keys
        for key in ["payload", "message", "text"]:
            if key in log_entry:
                val = log_entry[key]
                if isinstance(val, str):
                    return val.strip()
                elif isinstance(val, dict):
                    return self._extract_from_json(val)

        # Last resort: stringify the entry
        return str(log_entry)[:500]

    def _extract_from_json(self, payload: dict[str, Any]) -> str:
        """Extract message from JSON payload using heuristics."""
        if not isinstance(payload, dict):
            return str(payload)[:500]

        # Strategy 1: Check known message field names
        for field_name in MESSAGE_FIELD_NAMES:
            # Check exact match
            if field_name in payload:
                val = payload[field_name]
                if isinstance(val, str) and len(val) > 0:
                    return val.strip()

            # Check case-insensitive
            for key in payload:
                if key.lower() == field_name.lower():
                    val = payload[key]
                    if isinstance(val, str) and len(val) > 0:
                        return val.strip()

        # Strategy 2: Find longest string that looks like a log message
        best_candidate = None
        best_score = 0

        for key, val in payload.items():
            if isinstance(val, str) and len(val) > 10:
                score = self._score_message_candidate(key, val)
                if score > best_score:
                    best_score = score
                    best_candidate = val

        if best_candidate:
            return best_candidate.strip()

        # Strategy 3: Nested search for common patterns
        nested_msg = self._search_nested(payload, depth=2)
        if nested_msg:
            return nested_msg.strip()

        # Fallback: Compact JSON representation
        try:
            compact = json.dumps(payload, separators=(",", ":"))
            return compact[:500] if len(compact) > 500 else compact
        except Exception:
            return str(payload)[:500]

    def _extract_from_proto(self, payload: dict[str, Any]) -> str:
        """Extract message from audit log protoPayload."""
        if not isinstance(payload, dict):
            return str(payload)[:500]

        # Audit logs have specific structure
        parts = []

        # Method name
        if "methodName" in payload:
            parts.append(f"[{payload['methodName']}]")

        # Resource name
        if "resourceName" in payload:
            parts.append(payload["resourceName"])

        # Service name
        if "serviceName" in payload:
            parts.append(f"({payload['serviceName']})")

        # Status
        if "status" in payload:
            status = payload["status"]
            if isinstance(status, dict):
                code = status.get("code", "")
                message = status.get("message", "")
                if code or message:
                    parts.append(f"status={code}: {message}")

        if parts:
            return " ".join(parts)

        return str(payload)[:500]

    def _score_message_candidate(self, field_name: str, value: str) -> int:
        """Score how likely a field is to be the log message."""
        score = 0

        # Length bonus (longer is usually better, up to a point)
        if 20 < len(value) < 2000:
            score += min(len(value) // 20, 10)

        # Field name hints
        if any(name in field_name.lower() for name in ["msg", "log", "text", "error"]):
            score += 5

        # Pattern matching
        for pattern in self._pattern_re:
            if pattern.search(value):
                score += 3

        # Penalty for likely non-message fields
        if field_name.lower() in ["id", "timestamp", "time", "level", "severity"]:
            score -= 10

        # Penalty for UUIDs/IDs
        if re.match(r"^[a-f0-9-]{32,}$", value, re.IGNORECASE):
            score -= 5

        return score

    def _search_nested(self, obj: Any, depth: int = 2) -> str | None:
        """Recursively search for message fields in nested structures."""
        if depth <= 0:
            return None

        if isinstance(obj, dict):
            # Check common fields at this level
            for field_name in MESSAGE_FIELD_NAMES[:5]:  # Only top priority
                if field_name in obj:
                    val = obj[field_name]
                    if isinstance(val, str) and len(val) > 10:
                        return val

            # Recurse into nested dicts
            for val in obj.values():
                result = self._search_nested(val, depth - 1)
                if result:
                    return result

        elif isinstance(obj, list) and obj:
            # Check first element
            result = self._search_nested(obj[0], depth - 1)
            if result:
                return result

        return None


# Global extractor instance
_extractor = LogMessageExtractor()


def extract_log_message(log_entry: dict[str, Any]) -> str:
    """
    Extract the log message from a Cloud Logging entry.

    This is the main function to use for extracting messages. It handles
    textPayload, jsonPayload, and protoPayload formats automatically.

    Args:
        log_entry: A log entry dict from Cloud Logging

    Returns:
        The extracted log message string

    Example:
        >>> entry = {"textPayload": "User logged in successfully"}
        >>> extract_log_message(entry)
        'User logged in successfully'

        >>> entry = {"jsonPayload": {"message": "Request failed", "code": 500}}
        >>> extract_log_message(entry)
        'Request failed'
    """
    return _extractor.extract(log_entry)


def extract_messages_from_entries(
    log_entries: list[dict[str, Any]],
    include_metadata: bool = False,
) -> list[dict[str, Any]]:
    """
    Extract messages from a list of log entries.

    Args:
        log_entries: List of log entry dicts from Cloud Logging
        include_metadata: If True, include timestamp and severity

    Returns:
        List of dicts with 'message' and optionally 'timestamp', 'severity'
    """
    results = []

    for entry in log_entries:
        message = extract_log_message(entry)

        if include_metadata:
            results.append({
                "message": message,
                "timestamp": entry.get("timestamp", ""),
                "severity": entry.get("severity", ""),
                "resource": entry.get("resource", {}).get("type", "unknown"),
            })
        else:
            results.append({"message": message})

    return results
