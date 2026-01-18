"""Unit tests for Drain3 log pattern extraction.

Tests the pattern extraction, comparison, and anomaly detection
functionality using the Drain3 algorithm.
"""

from sre_agent.tools.analysis.logs.patterns import (
    LogPattern,
    LogPatternExtractor,
    PatternComparison,
    _determine_alert_level,
    _generate_recommendation,
    analyze_log_anomalies,
    compare_log_patterns,
    compare_patterns,
    extract_log_patterns,
    get_pattern_summary,
)


class TestLogPatternExtractor:
    """Tests for the LogPatternExtractor class."""

    def test_init_default_params(self):
        """Test extractor initialization with default parameters."""
        extractor = LogPatternExtractor()
        assert extractor.miner is not None
        assert extractor.patterns == {}

    def test_init_custom_params(self):
        """Test extractor initialization with custom parameters."""
        extractor = LogPatternExtractor(
            depth=6,
            sim_th=0.5,
            max_children=50,
            max_clusters=500,
        )
        assert extractor.miner is not None

    def test_add_single_log(self):
        """Test adding a single log message."""
        extractor = LogPatternExtractor()
        pattern_id = extractor.add_log(
            message="User 12345 logged in successfully",
            timestamp="2024-01-01T00:00:00Z",
            severity="INFO",
        )

        assert pattern_id != "unknown"
        assert len(extractor.patterns) == 1

    def test_add_multiple_similar_logs(self):
        """Test that similar logs cluster into same pattern."""
        extractor = LogPatternExtractor()

        # Add similar logs with more structure for better clustering
        ids = []
        for i in range(10):
            pattern_id = extractor.add_log(
                message=f"User logged in successfully from host-{i}",
                timestamp=f"2024-01-01T00:0{i}:00Z",
                severity="INFO",
            )
            ids.append(pattern_id)

        # Most should cluster together (Drain3 may split first few)
        unique_patterns = len(set(ids))
        assert unique_patterns <= 3, (
            f"Expected at most 3 patterns, got {unique_patterns}"
        )

        # Total count should match
        total_count = sum(p.count for p in extractor.patterns.values())
        assert total_count == 10

    def test_add_different_logs_creates_multiple_patterns(self):
        """Test that different logs create different patterns."""
        extractor = LogPatternExtractor()

        extractor.add_log(message="User logged in successfully")
        extractor.add_log(message="Database connection failed")
        extractor.add_log(message="Request timeout after 30 seconds")

        # Should have 3 different patterns
        assert len(extractor.patterns) >= 3

    def test_pattern_tracks_count(self):
        """Test that pattern count is tracked correctly."""
        extractor = LogPatternExtractor()

        for _ in range(5):
            extractor.add_log(message="Connection established to host-1234")

        pattern = next(iter(extractor.patterns.values()))
        assert pattern.count == 5

    def test_pattern_tracks_severity(self):
        """Test that severity counts are tracked."""
        extractor = LogPatternExtractor()

        extractor.add_log(message="Error occurred", severity="ERROR")
        extractor.add_log(message="Error occurred", severity="ERROR")
        extractor.add_log(message="Error occurred", severity="WARNING")

        pattern = next(iter(extractor.patterns.values()))
        assert pattern.severity_counts.get("ERROR", 0) == 2
        assert pattern.severity_counts.get("WARNING", 0) == 1

    def test_pattern_tracks_timestamps(self):
        """Test that first/last seen timestamps are tracked."""
        extractor = LogPatternExtractor()

        extractor.add_log(message="Event occurred", timestamp="2024-01-01T00:00:00Z")
        extractor.add_log(message="Event occurred", timestamp="2024-01-01T01:00:00Z")

        pattern = next(iter(extractor.patterns.values()))
        assert pattern.first_seen == "2024-01-01T00:00:00Z"
        assert pattern.last_seen == "2024-01-01T01:00:00Z"

    def test_pattern_stores_sample_messages(self):
        """Test that sample messages are stored (limited)."""
        extractor = LogPatternExtractor()

        for i in range(10):
            extractor.add_log(message=f"Request {i} completed in 50ms")

        pattern = next(iter(extractor.patterns.values()))
        # Should store up to 5 samples
        assert len(pattern.sample_messages) <= 5
        assert len(pattern.sample_messages) > 0

    def test_pattern_tracks_resources(self):
        """Test that resource types are tracked."""
        extractor = LogPatternExtractor()

        extractor.add_log(message="Log entry", resource="k8s_container")
        extractor.add_log(message="Log entry", resource="k8s_container")
        extractor.add_log(message="Log entry", resource="gce_instance")

        pattern = next(iter(extractor.patterns.values()))
        assert "k8s_container" in pattern.resources
        assert "gce_instance" in pattern.resources

    def test_get_patterns_with_min_count(self):
        """Test filtering patterns by minimum count."""
        extractor = LogPatternExtractor()

        for _ in range(10):
            extractor.add_log(message="Common pattern")
        for _ in range(2):
            extractor.add_log(message="Rare pattern occurs")

        patterns = extractor.get_patterns(min_count=5)
        assert len(patterns) == 1
        assert patterns[0].count == 10

    def test_get_patterns_sorted_by_count(self):
        """Test sorting patterns by count."""
        extractor = LogPatternExtractor()

        for _ in range(5):
            extractor.add_log(message="Medium pattern")
        for _ in range(10):
            extractor.add_log(message="High frequency pattern")
        for _ in range(2):
            extractor.add_log(message="Low frequency pattern")

        patterns = extractor.get_patterns(sort_by="count")
        assert patterns[0].count >= patterns[1].count >= patterns[2].count

    def test_get_patterns_sorted_by_severity(self):
        """Test sorting patterns by severity."""
        extractor = LogPatternExtractor()

        for _ in range(5):
            extractor.add_log(message="Info message", severity="INFO")
        for _ in range(3):
            extractor.add_log(message="Error message", severity="ERROR")
        for _ in range(1):
            extractor.add_log(message="Critical failure", severity="CRITICAL")

        patterns = extractor.get_patterns(sort_by="severity")
        # Critical/Error should come first
        assert (
            patterns[0].severity_counts.get("CRITICAL", 0) > 0
            or patterns[0].severity_counts.get("ERROR", 0) > 0
        )

    def test_get_patterns_with_limit(self):
        """Test limiting number of patterns returned."""
        extractor = LogPatternExtractor()

        # Create truly distinct patterns
        messages = [
            "Error occurred in database connection",
            "Warning: disk space is running low",
            "Info: user authentication successful",
            "Critical: server is not responding",
            "Debug: processing request started",
        ]
        for msg in messages:
            extractor.add_log(message=msg)

        patterns = extractor.get_patterns(limit=3)
        assert len(patterns) <= 3

    def test_get_summary_structure(self):
        """Test that summary has correct structure."""
        extractor = LogPatternExtractor()

        for i in range(20):
            severity = "ERROR" if i % 5 == 0 else "INFO"
            extractor.add_log(message=f"Log entry type {i % 3}", severity=severity)

        summary = extractor.get_summary(max_patterns=10)

        assert "total_logs_processed" in summary
        assert "unique_patterns" in summary
        assert "severity_distribution" in summary
        assert "compression_ratio" in summary
        assert "top_patterns" in summary
        assert "error_patterns" in summary

    def test_get_summary_compression_ratio(self):
        """Test compression ratio calculation."""
        extractor = LogPatternExtractor()

        # Add 100 logs that should compress to ~3 patterns
        for i in range(100):
            pattern_type = i % 3
            extractor.add_log(message=f"Pattern type {pattern_type} log entry {i}")

        summary = extractor.get_summary()
        assert summary["total_logs_processed"] == 100
        assert summary["compression_ratio"] > 1  # Should compress

    def test_masking_timestamps(self):
        """Test that timestamps are masked in patterns."""
        extractor = LogPatternExtractor()

        extractor.add_log(message="Request at 2024-01-01T10:30:45 completed")
        extractor.add_log(message="Request at 2024-01-02T14:22:33 completed")

        # Both should match same pattern (timestamps masked)
        assert len(extractor.patterns) == 1

    def test_masking_uuids(self):
        """Test that UUIDs are masked in patterns."""
        extractor = LogPatternExtractor()

        extractor.add_log(
            message="Processing request abc12345-def6-7890-abcd-ef1234567890"
        )
        extractor.add_log(
            message="Processing request 11111111-2222-3333-4444-555555555555"
        )

        # Both should match same pattern (UUIDs masked)
        assert len(extractor.patterns) == 1

    def test_masking_ip_addresses(self):
        """Test that IP addresses are masked in patterns."""
        extractor = LogPatternExtractor()

        extractor.add_log(message="Connection from 192.168.1.100 established")
        extractor.add_log(message="Connection from 10.0.0.50 established")

        # Both should match same pattern (IPs masked)
        assert len(extractor.patterns) == 1


class TestLogPattern:
    """Tests for the LogPattern dataclass."""

    def test_pattern_to_dict(self):
        """Test LogPattern to_dict serialization."""
        pattern = LogPattern(
            pattern_id="abc123",
            template="User <*> logged in",
            count=10,
            first_seen="2024-01-01T00:00:00Z",
            last_seen="2024-01-01T01:00:00Z",
            severity_counts={"INFO": 8, "ERROR": 2},
            sample_messages=["User 1 logged in", "User 2 logged in"],
            resources=["k8s_container", "k8s_container", "gce_instance"],
        )

        result = pattern.to_dict()

        assert result["pattern_id"] == "abc123"
        assert result["template"] == "User <*> logged in"
        assert result["count"] == 10
        assert len(result["sample_messages"]) <= 3
        assert len(result["resources"]) <= 5


class TestComparePatterns:
    """Tests for the compare_patterns function."""

    def test_detect_new_patterns(self):
        """Test detection of new patterns in period 2."""
        patterns1 = [
            LogPattern("p1", "Pattern A", 10),
        ]
        patterns2 = [
            LogPattern("p1", "Pattern A", 10),
            LogPattern("p2", "Pattern B (new)", 5),
        ]

        comparison = compare_patterns(patterns1, patterns2)

        assert len(comparison.new_patterns) == 1
        assert comparison.new_patterns[0].pattern_id == "p2"

    def test_detect_disappeared_patterns(self):
        """Test detection of patterns that disappeared."""
        patterns1 = [
            LogPattern("p1", "Pattern A", 10),
            LogPattern("p2", "Pattern B", 5),
        ]
        patterns2 = [
            LogPattern("p1", "Pattern A", 10),
        ]

        comparison = compare_patterns(patterns1, patterns2)

        assert len(comparison.disappeared_patterns) == 1
        assert comparison.disappeared_patterns[0].pattern_id == "p2"

    def test_detect_increased_patterns(self):
        """Test detection of significantly increased patterns."""
        # Need multiple patterns for rate calculation to be meaningful
        patterns1 = [
            LogPattern("p1", "Pattern A", 10),
            LogPattern("p2", "Pattern B", 90),  # Total: 100
        ]
        patterns2 = [
            LogPattern("p1", "Pattern A", 50),  # Increased rate: 10% -> 50%
            LogPattern("p2", "Pattern B", 50),  # Total: 100
        ]

        comparison = compare_patterns(patterns1, patterns2, significance_threshold=0.5)

        # Pattern A increased from 10% to 50% of traffic
        assert len(comparison.increased_patterns) >= 1

    def test_detect_decreased_patterns(self):
        """Test detection of significantly decreased patterns."""
        patterns1 = [
            LogPattern("p1", "Pattern A", 80),
            LogPattern("p2", "Pattern B", 20),  # Total: 100
        ]
        patterns2 = [
            LogPattern("p1", "Pattern A", 20),  # Decreased rate
            LogPattern("p2", "Pattern B", 80),  # Total: 100
        ]

        comparison = compare_patterns(patterns1, patterns2, significance_threshold=0.5)

        # Pattern A decreased from 80% to 20%
        assert len(comparison.decreased_patterns) >= 1

    def test_stable_patterns(self):
        """Test detection of stable patterns."""
        patterns1 = [
            LogPattern("p1", "Pattern A", 100),
        ]
        patterns2 = [
            LogPattern("p1", "Pattern A", 110),  # Only 10% change
        ]

        comparison = compare_patterns(patterns1, patterns2, significance_threshold=0.5)

        assert len(comparison.stable_patterns) == 1
        assert len(comparison.increased_patterns) == 0

    def test_comparison_to_dict(self):
        """Test PatternComparison to_dict serialization."""
        comparison = PatternComparison(
            new_patterns=[LogPattern("p1", "New", 5)],
            disappeared_patterns=[LogPattern("p2", "Gone", 3)],
            increased_patterns=[(LogPattern("p3", "More", 20), 150.0)],
            decreased_patterns=[(LogPattern("p4", "Less", 5), 50.0)],
            stable_patterns=[LogPattern("p5", "Same", 10)],
        )

        result = comparison.to_dict()

        assert len(result["new_patterns"]) == 1
        assert len(result["disappeared_patterns"]) == 1
        assert len(result["increased_patterns"]) == 1
        assert result["increased_patterns"][0]["increase_pct"] == 150.0
        assert result["stable_patterns_count"] == 1


class TestExtractLogPatterns:
    """Tests for the extract_log_patterns tool."""

    def test_extract_from_text_payload_logs(self, sample_text_payload_logs):
        """Test pattern extraction from textPayload logs."""
        result = extract_log_patterns(sample_text_payload_logs)

        assert "total_logs_processed" in result
        assert "unique_patterns" in result
        assert "top_patterns" in result
        assert result["total_logs_processed"] == len(sample_text_payload_logs)

    def test_extract_with_max_patterns(self, sample_text_payload_logs):
        """Test limiting max patterns returned."""
        result = extract_log_patterns(sample_text_payload_logs, max_patterns=2)

        assert len(result["top_patterns"]) <= 2

    def test_extract_with_min_count(self):
        """Test filtering by minimum count."""
        # Create logs with clear repetition
        logs = []
        for _i in range(10):
            logs.append(
                {
                    "textPayload": "Common pattern that repeats",
                    "severity": "INFO",
                }
            )
        logs.append(
            {
                "textPayload": "Unique pattern that appears once",
                "severity": "INFO",
            }
        )

        result = extract_log_patterns(logs, min_count=5)

        # Should only return patterns with count >= 5
        assert len(result["top_patterns"]) <= 2
        if result["top_patterns"]:
            assert result["top_patterns"][0]["count"] >= 5

    def test_extract_tracks_severity_distribution(self, sample_text_payload_logs):
        """Test that severity distribution is tracked."""
        result = extract_log_patterns(sample_text_payload_logs)

        assert "severity_distribution" in result
        severity_dist = result["severity_distribution"]
        # Should have INFO, ERROR, WARNING from sample logs
        assert any(s in severity_dist for s in ["INFO", "ERROR", "WARNING"])


class TestCompareLogPatterns:
    """Tests for the compare_log_patterns tool."""

    def test_compare_baseline_vs_incident(
        self, baseline_period_logs, incident_period_logs
    ):
        """Test comparing baseline vs incident period logs."""
        result = compare_log_patterns(
            baseline_entries_json=baseline_period_logs,
            comparison_entries_json=incident_period_logs,
        )

        assert "baseline_summary" in result
        assert "comparison_summary" in result
        assert "anomalies" in result
        assert "alert_level" in result

        # Should detect new error patterns
        anomalies = result["anomalies"]
        assert len(anomalies.get("new_patterns", [])) > 0

    def test_compare_identical_periods(self, baseline_period_logs):
        """Test comparing identical log sets."""
        result = compare_log_patterns(
            baseline_entries_json=baseline_period_logs,
            comparison_entries_json=baseline_period_logs,
        )

        anomalies = result["anomalies"]
        # Should have no new patterns
        assert len(anomalies.get("new_patterns", [])) == 0
        # Should have no disappeared patterns
        assert len(anomalies.get("disappeared_patterns", [])) == 0

    def test_compare_with_significance_threshold(
        self, baseline_period_logs, incident_period_logs
    ):
        """Test significance threshold affects results."""
        # High threshold - fewer significant changes
        result_high = compare_log_patterns(
            baseline_entries_json=baseline_period_logs,
            comparison_entries_json=incident_period_logs,
            significance_threshold=0.9,
        )

        # Low threshold - more significant changes
        result_low = compare_log_patterns(
            baseline_entries_json=baseline_period_logs,
            comparison_entries_json=incident_period_logs,
            significance_threshold=0.1,
        )

        # Low threshold should detect more changes
        high_changes = len(result_high["anomalies"].get("increased_patterns", []))
        low_changes = len(result_low["anomalies"].get("increased_patterns", []))
        assert low_changes >= high_changes


class TestAnalyzeLogAnomalies:
    """Tests for the analyze_log_anomalies tool."""

    def test_analyze_error_logs(self, incident_period_logs):
        """Test anomaly analysis focused on errors."""
        result = analyze_log_anomalies(incident_period_logs, focus_on_errors=True)

        assert "total_logs" in result
        assert "unique_patterns" in result
        assert "error_patterns" in result
        assert "recommendation" in result

    def test_analyze_all_logs(self, sample_text_payload_logs):
        """Test anomaly analysis without error focus."""
        result = analyze_log_anomalies(sample_text_payload_logs, focus_on_errors=False)

        assert "top_patterns" in result
        assert len(result["top_patterns"]) > 0

    def test_analyze_with_max_results(self, incident_period_logs):
        """Test limiting max results."""
        result = analyze_log_anomalies(incident_period_logs, max_results=3)

        assert len(result["top_patterns"]) <= 3

    def test_recommendation_generation(self, incident_period_logs):
        """Test that recommendations are generated."""
        result = analyze_log_anomalies(incident_period_logs)

        assert "recommendation" in result
        assert isinstance(result["recommendation"], str)
        assert len(result["recommendation"]) > 0


class TestGetPatternSummary:
    """Tests for the get_pattern_summary function."""

    def test_summary_empty_patterns(self):
        """Test summary with no patterns."""
        summary = get_pattern_summary([])
        assert "No patterns found" in summary

    def test_summary_with_patterns(self):
        """Test summary with patterns."""
        patterns = [
            LogPattern("p1", "Error in service", 100, severity_counts={"ERROR": 100}),
            LogPattern("p2", "Request completed", 50, severity_counts={"INFO": 50}),
        ]

        summary = get_pattern_summary(patterns)

        assert "2 unique patterns" in summary
        assert "(100x)" in summary  # Count of first pattern

    def test_summary_respects_max_length(self):
        """Test that summary respects max_length."""
        patterns = [LogPattern(f"p{i}", f"Pattern {i} " * 50, 10) for i in range(20)]

        summary = get_pattern_summary(patterns, max_length=500)

        assert len(summary) <= 600  # Some buffer for truncation message


class TestAlertLevelDetermination:
    """Tests for alert level determination."""

    def test_high_alert_new_error_patterns(self):
        """Test HIGH alert for new error patterns."""
        comparison = PatternComparison(
            new_patterns=[
                LogPattern("p1", "New error", 10, severity_counts={"ERROR": 10})
            ],
            disappeared_patterns=[],
            increased_patterns=[],
            decreased_patterns=[],
            stable_patterns=[],
        )

        alert = _determine_alert_level(comparison)
        assert "HIGH" in alert or "🔴" in alert

    def test_medium_alert_many_new_patterns(self):
        """Test MEDIUM alert for many new patterns."""
        comparison = PatternComparison(
            new_patterns=[
                LogPattern(f"p{i}", f"New pattern {i}", 5) for i in range(10)
            ],
            disappeared_patterns=[],
            increased_patterns=[],
            decreased_patterns=[],
            stable_patterns=[],
        )

        alert = _determine_alert_level(comparison)
        assert "MEDIUM" in alert or "🟠" in alert

    def test_low_alert_no_significant_changes(self):
        """Test LOW alert when no significant changes."""
        comparison = PatternComparison(
            new_patterns=[],
            disappeared_patterns=[],
            increased_patterns=[],
            decreased_patterns=[],
            stable_patterns=[LogPattern("p1", "Stable", 100)],
        )

        alert = _determine_alert_level(comparison)
        assert "LOW" in alert or "🟢" in alert


class TestRecommendationGeneration:
    """Tests for recommendation generation."""

    def test_recommendation_for_critical(self):
        """Test recommendation for critical patterns."""
        critical = [
            LogPattern("p1", "Critical failure", 10, severity_counts={"CRITICAL": 10})
        ]

        rec = _generate_recommendation(critical, [], [])
        assert "CRITICAL" in rec
        assert "investigate" in rec.lower()

    def test_recommendation_for_errors(self):
        """Test recommendation for error patterns."""
        errors = [LogPattern("p1", "Error occurred", 50, severity_counts={"ERROR": 50})]

        rec = _generate_recommendation([], errors, [])
        assert "ERROR" in rec or "error" in rec.lower()

    def test_recommendation_for_warnings(self):
        """Test recommendation for warning patterns."""
        warnings = [
            LogPattern("p1", "Warning message", 20, severity_counts={"WARNING": 20})
        ]

        rec = _generate_recommendation([], [], warnings)
        assert "WARNING" in rec or "warning" in rec.lower()

    def test_recommendation_healthy(self):
        """Test recommendation when logs look healthy."""
        rec = _generate_recommendation([], [], [])
        assert "healthy" in rec.lower() or "✅" in rec
