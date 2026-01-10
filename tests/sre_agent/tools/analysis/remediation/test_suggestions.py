"""Tests for remediation suggestion tools."""

import json

import pytest


class TestRemediationSuggestions:
    """Test suite for remediation suggestion tools."""

    def test_generate_remediation_for_oom(self):
        """Test that OOM pattern generates memory-related suggestions."""
        from sre_agent.tools.analysis.remediation.suggestions import (
            generate_remediation_suggestions,
        )

        result = generate_remediation_suggestions(
            "Container frontend-pod is repeatedly OOMKilled"
        )
        result_data = json.loads(result)

        assert "matched_patterns" in result_data
        assert "oom_killed" in result_data["matched_patterns"]
        assert "suggestions" in result_data
        assert len(result_data["suggestions"]) > 0

        # Should suggest increasing memory
        suggestion_actions = [s["action"] for s in result_data["suggestions"]]
        assert any("memory" in action.lower() for action in suggestion_actions)

    def test_generate_remediation_for_connection_pool(self):
        """Test that connection pool pattern generates DB suggestions."""
        from sre_agent.tools.analysis.remediation.suggestions import (
            generate_remediation_suggestions,
        )

        result = generate_remediation_suggestions(
            "Database connection pool exhausted"
        )
        result_data = json.loads(result)

        assert "connection_pool" in result_data["matched_patterns"]
        assert any(
            s["category"] == "database" for s in result_data["suggestions"]
        )

    def test_generate_remediation_for_high_latency(self):
        """Test that latency pattern generates performance suggestions."""
        from sre_agent.tools.analysis.remediation.suggestions import (
            generate_remediation_suggestions,
        )

        result = generate_remediation_suggestions(
            "P99 latency spike to 2000ms, timeouts occurring"
        )
        result_data = json.loads(result)

        assert "high_latency" in result_data["matched_patterns"]
        assert any(
            s["category"] == "performance" for s in result_data["suggestions"]
        )

    def test_generate_remediation_for_unknown_pattern(self):
        """Test that unknown patterns get generic suggestions."""
        from sre_agent.tools.analysis.remediation.suggestions import (
            generate_remediation_suggestions,
        )

        result = generate_remediation_suggestions(
            "Some unknown issue with xyz"
        )
        result_data = json.loads(result)

        assert len(result_data["matched_patterns"]) == 0
        assert "suggestions" in result_data
        assert "note" in result_data

    def test_quick_wins_are_identified(self):
        """Test that low-risk, low-effort suggestions are marked as quick wins."""
        from sre_agent.tools.analysis.remediation.suggestions import (
            generate_remediation_suggestions,
        )

        result = generate_remediation_suggestions(
            "Container is repeatedly OOMKilled"
        )
        result_data = json.loads(result)

        assert "quick_wins" in result_data
        for quick_win in result_data["quick_wins"]:
            assert quick_win["risk"] == "low"
            assert quick_win["effort"] == "low"


class TestGcloudCommands:
    """Test suite for gcloud command generation."""

    def test_scale_up_command_generation(self):
        """Test that scale_up generates correct gcloud command."""
        from sre_agent.tools.analysis.remediation.suggestions import (
            get_gcloud_commands,
        )

        result = get_gcloud_commands(
            "scale_up",
            "frontend-service",
            "my-project",
            region="us-central1",
            replicas=5,
        )
        result_data = json.loads(result)

        assert "commands" in result_data
        assert len(result_data["commands"]) > 0

        command = result_data["commands"][0]["command"]
        assert "gcloud run services update" in command
        assert "frontend-service" in command
        assert "--min-instances=5" in command
        assert "us-central1" in command

    def test_rollback_command_generation(self):
        """Test that rollback generates correct gcloud command."""
        from sre_agent.tools.analysis.remediation.suggestions import (
            get_gcloud_commands,
        )

        result = get_gcloud_commands(
            "rollback",
            "frontend-service",
            "my-project",
            region="us-central1",
        )
        result_data = json.loads(result)

        assert "commands" in result_data
        commands = [c["command"] for c in result_data["commands"]]
        assert any("update-traffic" in cmd for cmd in commands)

    def test_increase_memory_command_generation(self):
        """Test that increase_memory generates correct gcloud command."""
        from sre_agent.tools.analysis.remediation.suggestions import (
            get_gcloud_commands,
        )

        result = get_gcloud_commands(
            "increase_memory",
            "api-service",
            "my-project",
            region="us-central1",
            memory="2Gi",
        )
        result_data = json.loads(result)

        command = result_data["commands"][0]["command"]
        assert "--memory=2Gi" in command

    def test_unknown_remediation_type(self):
        """Test that unknown remediation type returns available types."""
        from sre_agent.tools.analysis.remediation.suggestions import (
            get_gcloud_commands,
        )

        result = get_gcloud_commands(
            "unknown_type",
            "service",
            "project",
        )
        result_data = json.loads(result)

        assert "error" in result_data
        assert "available_types" in result_data


class TestRiskEstimation:
    """Test suite for remediation risk estimation."""

    def test_low_risk_actions(self):
        """Test that scaling up is classified as low risk."""
        from sre_agent.tools.analysis.remediation.suggestions import (
            estimate_remediation_risk,
        )

        result = estimate_remediation_risk(
            "scale up replicas",
            "frontend-service",
            "Increase replicas from 3 to 5",
        )
        result_data = json.loads(result)

        assert result_data["risk_assessment"]["level"] == "low"
        assert result_data["recommendations"]["proceed"] is True

    def test_high_risk_actions(self):
        """Test that database migration is classified as high risk."""
        from sre_agent.tools.analysis.remediation.suggestions import (
            estimate_remediation_risk,
        )

        result = estimate_remediation_risk(
            "database migration",
            "main-db",
            "Migrate schema to new version",
        )
        result_data = json.loads(result)

        assert result_data["risk_assessment"]["level"] == "high"
        assert result_data["recommendations"]["require_approval"] is True

    def test_risk_factors_for_database(self):
        """Test that database changes get appropriate risk factors."""
        from sre_agent.tools.analysis.remediation.suggestions import (
            estimate_remediation_risk,
        )

        result = estimate_remediation_risk(
            "modify database config",
            "main-db",
            "Increase max connections",
        )
        result_data = json.loads(result)

        risk_factors = result_data["risk_assessment"]["factors"]
        assert any("data integrity" in f.lower() for f in risk_factors)

    def test_checklist_is_provided(self):
        """Test that a checklist is always provided."""
        from sre_agent.tools.analysis.remediation.suggestions import (
            estimate_remediation_risk,
        )

        result = estimate_remediation_risk(
            "scale up",
            "service",
            "Add replicas",
        )
        result_data = json.loads(result)

        assert "checklist" in result_data
        assert len(result_data["checklist"]) > 0


class TestSimilarIncidents:
    """Test suite for similar incident lookup."""

    def test_find_oom_incidents(self):
        """Test finding similar OOM incidents."""
        from sre_agent.tools.analysis.remediation.suggestions import (
            find_similar_past_incidents,
        )

        result = find_similar_past_incidents("OOMKilled")
        result_data = json.loads(result)

        assert "matches_found" in result_data
        assert result_data["matches_found"] > 0
        assert "similar_incidents" in result_data

    def test_find_timeout_incidents(self):
        """Test finding similar timeout incidents."""
        from sre_agent.tools.analysis.remediation.suggestions import (
            find_similar_past_incidents,
        )

        result = find_similar_past_incidents("timeout errors")
        result_data = json.loads(result)

        assert result_data["matches_found"] > 0

    def test_no_matches_returns_note(self):
        """Test that no matches returns helpful note."""
        from sre_agent.tools.analysis.remediation.suggestions import (
            find_similar_past_incidents,
        )

        result = find_similar_past_incidents("xyz123_unique_error")
        result_data = json.loads(result)

        # Either no matches or partial matches
        if result_data["matches_found"] == 0:
            assert "note" in result_data

    def test_key_learnings_included(self):
        """Test that key learnings are extracted from matches."""
        from sre_agent.tools.analysis.remediation.suggestions import (
            find_similar_past_incidents,
        )

        result = find_similar_past_incidents("connection pool")
        result_data = json.loads(result)

        if result_data["matches_found"] > 0:
            assert "key_learnings" in result_data
            assert len(result_data["key_learnings"]) > 0
