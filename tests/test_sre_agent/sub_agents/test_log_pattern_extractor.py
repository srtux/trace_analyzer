"""Integration tests for the log_pattern_extractor sub-agent.

These tests verify the integration between the log pattern extraction
tools and the sub-agent workflow.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta, timezone

from sre_agent.tools.logs.patterns import (
    extract_log_patterns,
    compare_log_patterns,
    analyze_log_anomalies,
)
from sre_agent.tools.logs.extraction import (
    extract_log_message,
    extract_messages_from_entries,
)


class TestLogPatternAnalysisWorkflow:
    """Integration tests for the log pattern analysis workflow."""

    def test_full_pattern_extraction_workflow(
        self, sample_text_payload_logs
    ):
        """Test complete pattern extraction from raw logs."""
        # Step 1: Extract messages
        messages = extract_messages_from_entries(sample_text_payload_logs)
        assert len(messages) == len(sample_text_payload_logs)

        # Step 2: Extract patterns
        result = extract_log_patterns(sample_text_payload_logs)

        # Verify workflow produced expected results
        assert result["total_logs_processed"] == len(sample_text_payload_logs)
        assert result["unique_patterns"] > 0
        assert result["compression_ratio"] >= 1.0

    def test_incident_detection_workflow(
        self, baseline_period_logs, incident_period_logs
    ):
        """Test complete incident detection workflow."""
        # Step 1: Extract patterns from baseline
        baseline_result = extract_log_patterns(baseline_period_logs)
        assert baseline_result["total_logs_processed"] > 0

        # Step 2: Extract patterns from incident period
        incident_result = extract_log_patterns(incident_period_logs)
        assert incident_result["total_logs_processed"] > 0

        # Step 3: Compare patterns to find anomalies
        comparison = compare_log_patterns(
            baseline_entries=baseline_period_logs,
            comparison_entries=incident_period_logs,
        )

        # Verify new error patterns detected
        assert "anomalies" in comparison
        anomalies = comparison["anomalies"]

        # Should detect new patterns that appeared during incident
        assert len(anomalies.get("new_patterns", [])) > 0

        # Alert level should be elevated
        assert comparison["alert_level"] != ""

    def test_error_triage_workflow(self, incident_period_logs):
        """Test error-focused triage workflow."""
        # Step 1: Analyze for anomalies with error focus
        result = analyze_log_anomalies(
            incident_period_logs,
            focus_on_errors=True,
            max_results=10,
        )

        # Step 2: Verify error patterns are prioritized
        assert "error_patterns" in result
        assert "recommendation" in result

        # Should have actionable recommendation
        assert len(result["recommendation"]) > 0

    def test_pattern_compression_effectiveness(self):
        """Test that pattern extraction achieves meaningful compression."""
        # Generate repetitive logs
        logs = []
        base_time = datetime.now(timezone.utc)

        # 100 similar login messages
        for i in range(100):
            logs.append({
                "timestamp": (base_time + timedelta(seconds=i)).isoformat() + "Z",
                "severity": "INFO",
                "textPayload": f"User {i * 1000 + 12345} logged in from 192.168.{i % 256}.{i % 256}",
                "resource": {"type": "k8s_container"},
            })

        # 50 similar error messages
        for i in range(50):
            logs.append({
                "timestamp": (base_time + timedelta(seconds=100 + i)).isoformat() + "Z",
                "severity": "ERROR",
                "textPayload": f"Connection timeout to host-{i}:5432 after 30000ms",
                "resource": {"type": "k8s_container"},
            })

        result = extract_log_patterns(logs)

        # Should compress 150 logs into ~2-3 patterns
        assert result["total_logs_processed"] == 150
        assert result["unique_patterns"] <= 5
        assert result["compression_ratio"] >= 30  # At least 30:1 compression

    def test_mixed_severity_analysis(self):
        """Test analysis of logs with mixed severity levels."""
        logs = [
            {"textPayload": "Info message 1", "severity": "INFO"},
            {"textPayload": "Info message 2", "severity": "INFO"},
            {"textPayload": "Warning about something", "severity": "WARNING"},
            {"textPayload": "Error occurred in service", "severity": "ERROR"},
            {"textPayload": "Error occurred in service", "severity": "ERROR"},
            {"textPayload": "Critical failure detected", "severity": "CRITICAL"},
        ]

        result = analyze_log_anomalies(logs, focus_on_errors=True)

        # Should categorize by severity
        assert "critical_patterns" in result
        assert "error_patterns" in result
        assert "warning_patterns" in result

        # Critical patterns should be flagged
        assert len(result["critical_patterns"]) > 0 or "CRITICAL" in result["recommendation"]


class TestLogPatternToolIntegration:
    """Tests for tool integration in the log pattern workflow."""

    def test_tools_work_with_empty_logs(self):
        """Test that tools handle empty log lists gracefully."""
        result = extract_log_patterns([])
        assert result["total_logs_processed"] == 0
        assert result["unique_patterns"] == 0

        comparison = compare_log_patterns([], [])
        assert comparison["baseline_summary"]["total_logs"] == 0

        anomalies = analyze_log_anomalies([])
        assert anomalies["total_logs"] == 0

    def test_tools_handle_malformed_entries(self):
        """Test that tools handle malformed log entries."""
        logs = [
            {"textPayload": "Valid message", "severity": "INFO"},
            {},  # Empty entry
            {"severity": "ERROR"},  # Missing payload
            {"textPayload": "", "severity": "INFO"},  # Empty message
        ]

        # Should not raise exceptions
        result = extract_log_patterns(logs)
        assert result["total_logs_processed"] == 4

    def test_json_payload_field_detection(self, sample_json_payload_logs):
        """Test that JSON payload fields are correctly detected."""
        result = extract_log_patterns(sample_json_payload_logs)

        # Should successfully extract patterns from JSON logs
        assert result["total_logs_processed"] == len(sample_json_payload_logs)
        assert result["unique_patterns"] > 0

    def test_pattern_stability_across_runs(self, sample_text_payload_logs):
        """Test that pattern extraction is deterministic."""
        result1 = extract_log_patterns(sample_text_payload_logs)
        result2 = extract_log_patterns(sample_text_payload_logs)

        # Should produce same number of patterns
        assert result1["unique_patterns"] == result2["unique_patterns"]
        assert result1["total_logs_processed"] == result2["total_logs_processed"]


class TestSubAgentConfiguration:
    """Tests for the log_pattern_extractor sub-agent configuration."""

    def test_subagent_has_required_tools(self):
        """Test that sub-agent has all required tools configured."""
        from sre_agent.sub_agents.log_analysis.agents import log_pattern_extractor

        tool_names = [t.__name__ if hasattr(t, '__name__') else str(t)
                      for t in log_pattern_extractor.tools]

        # Should have log fetching tools
        assert any("log" in name.lower() for name in tool_names)

        # Should have pattern extraction tools
        assert any("pattern" in name.lower() for name in tool_names)

    def test_subagent_has_instruction(self):
        """Test that sub-agent has proper instruction configured."""
        from sre_agent.sub_agents.log_analysis.agents import log_pattern_extractor

        assert log_pattern_extractor.instruction is not None
        assert len(log_pattern_extractor.instruction) > 100

        # Should mention key capabilities
        instruction = log_pattern_extractor.instruction.lower()
        assert "drain3" in instruction or "pattern" in instruction
        assert "log" in instruction

    def test_subagent_model_configuration(self):
        """Test that sub-agent uses appropriate model."""
        from sre_agent.sub_agents.log_analysis.agents import log_pattern_extractor

        assert log_pattern_extractor.model is not None
        # Should use Gemini model
        assert "gemini" in log_pattern_extractor.model.lower()


class TestMainAgentIntegration:
    """Tests for integration with the main SRE Agent."""

    def test_main_agent_has_log_pattern_extractor(self):
        """Test that main agent includes log_pattern_extractor sub-agent."""
        from sre_agent.agent import sre_agent

        sub_agent_names = [sa.name for sa in sre_agent.sub_agents]
        assert "log_pattern_extractor" in sub_agent_names

    def test_main_agent_has_log_pattern_tools(self):
        """Test that main agent has log pattern tools."""
        from sre_agent.agent import base_tools

        tool_names = [t.__name__ if hasattr(t, '__name__') else str(t)
                      for t in base_tools]

        # Should have pattern extraction tools
        assert "extract_log_patterns" in tool_names
        assert "compare_log_patterns" in tool_names
        assert "analyze_log_anomalies" in tool_names

    def test_main_agent_prompt_mentions_log_analysis(self):
        """Test that main agent prompt mentions log analysis capabilities."""
        from sre_agent.prompt import SRE_AGENT_PROMPT

        prompt_lower = SRE_AGENT_PROMPT.lower()

        # Should mention log analysis capabilities
        assert "log" in prompt_lower
        assert "pattern" in prompt_lower
        assert "drain3" in prompt_lower or "extraction" in prompt_lower
