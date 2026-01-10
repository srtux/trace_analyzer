"""Tests for metrics sub-agent."""

from sre_agent.sub_agents.metrics import metrics_analyzer


def test_metrics_analyzer_initialization():
    assert metrics_analyzer.name == "metrics_analyzer"
    assert "metrics" in metrics_analyzer.description


def test_metrics_analyzer_tools():
    tool_names = [getattr(t, "name", t.__name__) for t in metrics_analyzer.tools]
    assert "list_time_series" in tool_names
    assert "query_promql" in tool_names
    assert "detect_metric_anomalies" in tool_names
    assert "compare_metric_windows" in tool_names
    assert "calculate_series_stats" in tool_names
