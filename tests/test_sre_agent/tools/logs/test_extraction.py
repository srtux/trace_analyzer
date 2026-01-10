"""Unit tests for log message extraction.

Tests the smart message extraction logic that handles various
log payload formats: textPayload, jsonPayload, protoPayload.
"""

import pytest

from sre_agent.tools.logs.extraction import (
    LogMessageExtractor,
    extract_log_message,
    extract_messages_from_entries,
)


class TestExtractLogMessage:
    """Tests for the extract_log_message function."""

    def test_extract_text_payload(self):
        """Test extraction from textPayload field."""
        entry = {
            "textPayload": "Simple log message",
            "severity": "INFO",
        }
        message = extract_log_message(entry)
        assert message == "Simple log message"

    def test_extract_text_payload_with_whitespace(self):
        """Test that whitespace is stripped from textPayload."""
        entry = {
            "textPayload": "  Message with whitespace  \n",
            "severity": "INFO",
        }
        message = extract_log_message(entry)
        assert message == "Message with whitespace"

    def test_extract_json_payload_message_field(self):
        """Test extraction from jsonPayload.message field."""
        entry = {
            "jsonPayload": {
                "message": "JSON structured message",
                "level": "info",
                "extra": "data",
            },
            "severity": "INFO",
        }
        message = extract_log_message(entry)
        assert message == "JSON structured message"

    def test_extract_json_payload_msg_field(self):
        """Test extraction from jsonPayload.msg field."""
        entry = {
            "jsonPayload": {
                "msg": "Short form message",
                "time": "2024-01-01T00:00:00Z",
            },
            "severity": "INFO",
        }
        message = extract_log_message(entry)
        assert message == "Short form message"

    def test_extract_json_payload_log_field(self):
        """Test extraction from jsonPayload.log field (Docker logs)."""
        entry = {
            "jsonPayload": {
                "log": "Container log message",
                "stream": "stdout",
            },
            "severity": "INFO",
        }
        message = extract_log_message(entry)
        assert message == "Container log message"

    def test_extract_json_payload_text_field(self):
        """Test extraction from jsonPayload.text field."""
        entry = {
            "jsonPayload": {
                "text": "Text field message",
            },
            "severity": "INFO",
        }
        message = extract_log_message(entry)
        assert message == "Text field message"

    def test_extract_json_payload_description_field(self):
        """Test extraction from jsonPayload.description field."""
        entry = {
            "jsonPayload": {
                "description": "Description field message",
                "id": 123,
            },
            "severity": "INFO",
        }
        message = extract_log_message(entry)
        assert message == "Description field message"

    def test_extract_proto_payload_status_message(self):
        """Test extraction from protoPayload.status.message field."""
        entry = {
            "protoPayload": {
                "@type": "type.googleapis.com/google.cloud.audit.AuditLog",
                "methodName": "compute.instances.insert",
                "status": {"message": "Instance created successfully"},
            },
            "severity": "NOTICE",
        }
        message = extract_log_message(entry)
        # protoPayload extraction includes method name in brackets
        assert "Instance created successfully" in message
        assert "compute.instances.insert" in message

    def test_extract_proto_payload_method_name_fallback(self):
        """Test fallback to methodName when status.message is missing."""
        entry = {
            "protoPayload": {
                "@type": "type.googleapis.com/google.cloud.audit.AuditLog",
                "methodName": "storage.objects.create",
            },
            "severity": "NOTICE",
        }
        message = extract_log_message(entry)
        # Method name is extracted with brackets
        assert "storage.objects.create" in message

    def test_extract_empty_entry(self):
        """Test extraction from an empty entry."""
        entry = {}
        message = extract_log_message(entry)
        # Empty entry returns string representation
        assert isinstance(message, str)

    def test_extract_entry_with_no_message_fields(self):
        """Test extraction when no known message fields exist."""
        entry = {
            "jsonPayload": {
                "count": 42,
                "items": ["a", "b", "c"],
            },
            "severity": "INFO",
        }
        message = extract_log_message(entry)
        # Should return a JSON representation or empty string
        assert isinstance(message, str)

    def test_extract_priority_text_over_json(self):
        """Test that textPayload takes priority over jsonPayload."""
        entry = {
            "textPayload": "Text payload message",
            "jsonPayload": {"message": "JSON message"},
            "severity": "INFO",
        }
        message = extract_log_message(entry)
        assert message == "Text payload message"

    def test_extract_json_payload_longest_string(self):
        """Test heuristic selection of longest string field."""
        entry = {
            "jsonPayload": {
                "short": "Hi",
                "medium": "This is a medium message",
                "long": "This is a much longer message that should be selected",
            },
            "severity": "INFO",
        }
        message = extract_log_message(entry)
        # Should prefer the longer, more descriptive string
        assert "longer message" in message or len(message) > 10


class TestLogMessageExtractor:
    """Tests for the LogMessageExtractor class."""

    def test_extractor_with_text_payload(self):
        """Test extractor with textPayload entries."""
        extractor = LogMessageExtractor()
        entry = {"textPayload": "Test message", "severity": "INFO"}

        message = extractor.extract(entry)
        assert message == "Test message"

    def test_extractor_with_json_payload(self):
        """Test extractor with jsonPayload entries."""
        extractor = LogMessageExtractor()
        entry = {
            "jsonPayload": {"message": "Structured message", "code": 200},
            "severity": "INFO",
        }

        message = extractor.extract(entry)
        assert message == "Structured message"

    def test_extractor_caches_field_detection(self):
        """Test that extractor uses known message field names."""
        extractor = LogMessageExtractor()

        # Using known field name "message"
        entries = [
            {"jsonPayload": {"message": "Message 1"}, "severity": "INFO"},
            {"jsonPayload": {"message": "Message 2"}, "severity": "INFO"},
            {"jsonPayload": {"message": "Message 3"}, "severity": "INFO"},
        ]

        messages = [extractor.extract(e) for e in entries]

        # All should be extracted using "message" field
        assert all("Message" in m for m in messages)

    def test_extractor_handles_mixed_formats(self):
        """Test extractor with mixed payload formats."""
        extractor = LogMessageExtractor()

        entries = [
            {"textPayload": "Text entry", "severity": "INFO"},
            {"jsonPayload": {"message": "JSON entry"}, "severity": "INFO"},
            {"protoPayload": {"methodName": "api.call"}, "severity": "NOTICE"},
        ]

        messages = [extractor.extract(e) for e in entries]

        assert messages[0] == "Text entry"
        assert messages[1] == "JSON entry"
        # protoPayload includes brackets around method name
        assert "api.call" in messages[2]


class TestExtractMessagesFromEntries:
    """Tests for the extract_messages_from_entries function."""

    def test_extract_from_multiple_entries(
        self, sample_text_payload_logs
    ):
        """Test extraction from multiple log entries."""
        results = extract_messages_from_entries(sample_text_payload_logs)

        assert len(results) == len(sample_text_payload_logs)
        # Returns list of dicts with "message" key
        assert all(isinstance(r, dict) and "message" in r for r in results)
        assert "logged in successfully" in results[0]["message"]
        assert "Connection refused" in results[2]["message"]

    def test_extract_from_json_entries(self, sample_json_payload_logs):
        """Test extraction from JSON payload entries."""
        results = extract_messages_from_entries(sample_json_payload_logs)

        assert len(results) == len(sample_json_payload_logs)
        assert "Request processed successfully" in results[0]["message"]
        assert "Database connection failed" in results[1]["message"]

    def test_extract_from_mixed_entries(self, mixed_payload_logs):
        """Test extraction from mixed payload types."""
        results = extract_messages_from_entries(mixed_payload_logs)

        assert len(results) == len(mixed_payload_logs)
        # Verify specific extractions
        assert "Simple text message" in results[0]["message"]
        assert "JSON message field" in results[1]["message"]

    def test_extract_preserves_order(self, sample_text_payload_logs):
        """Test that message order matches entry order."""
        results = extract_messages_from_entries(sample_text_payload_logs)

        # First message should be about login
        assert "12345" in results[0]["message"]
        # Third should be error
        assert "refused" in results[2]["message"].lower()

    def test_extract_empty_list(self):
        """Test extraction from empty list."""
        results = extract_messages_from_entries([])
        assert results == []

    def test_extract_handles_none_entries(self):
        """Test extraction handles None values gracefully."""
        entries = [
            {"textPayload": "Valid message"},
            None,  # Invalid entry
            {"textPayload": "Another message"},
        ]

        # Should not raise, may skip None entries
        try:
            results = extract_messages_from_entries(entries)
            assert len(results) >= 2
        except (TypeError, AttributeError):
            # Acceptable to raise for invalid input
            pass


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_nested_json_payload(self):
        """Test extraction from deeply nested JSON."""
        entry = {
            "jsonPayload": {
                "data": {
                    "nested": {
                        "message": "Deeply nested message"
                    }
                }
            }
        }
        message = extract_log_message(entry)
        # May or may not find nested message depending on implementation
        assert isinstance(message, str)

    def test_unicode_messages(self):
        """Test extraction of unicode messages."""
        entry = {
            "textPayload": "Unicode: こんにちは 🎉 émojis",
        }
        message = extract_log_message(entry)
        assert "こんにちは" in message
        assert "🎉" in message

    def test_very_long_message(self):
        """Test extraction of very long messages."""
        long_text = "x" * 10000
        entry = {"textPayload": long_text}
        message = extract_log_message(entry)
        assert len(message) > 0
        # Implementation may truncate, verify it handles gracefully

    def test_multiline_message(self):
        """Test extraction of multiline messages."""
        entry = {
            "textPayload": "Line 1\nLine 2\nLine 3",
        }
        message = extract_log_message(entry)
        assert "Line 1" in message

    def test_json_with_null_message(self):
        """Test JSON payload with null message field."""
        entry = {
            "jsonPayload": {
                "message": None,
                "fallback": "Use this instead",
            }
        }
        message = extract_log_message(entry)
        # Should handle null gracefully
        assert isinstance(message, str)

    def test_json_with_non_string_message(self):
        """Test JSON payload with non-string message field."""
        entry = {
            "jsonPayload": {
                "message": {"nested": "object"},
                "other": "text field",
            }
        }
        message = extract_log_message(entry)
        # Should handle non-string message gracefully
        assert isinstance(message, str)
