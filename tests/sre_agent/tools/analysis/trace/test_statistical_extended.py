from unittest.mock import patch

from sre_agent.tools.analysis.trace.statistical_analysis import (
    analyze_critical_path,
    analyze_trace_patterns,
    detect_latency_anomalies,
    perform_causal_analysis,
)


@patch("sre_agent.tools.analysis.trace.statistical_analysis.fetch_trace_data")
def test_analyze_critical_path_success(mock_fetch):
    # Create a simple trace: Root -> Child (blocking)
    # Root: 0-100ms
    # Child: 10-98ms (88ms). Gap = 2ms (<5ms threshold).
    # Self time of root = 100 - 88 = 12ms.
    # Critical blocking = 88ms.
    # Total = 12 + 88 = 100ms.
    trace_data = {
        "spans": [
            {
                "span_id": "root",
                "name": "root_span",
                "start_time": "2024-01-01T10:00:00.000Z",
                "end_time": "2024-01-01T10:00:00.100Z",
                "parent_span_id": None,
            },
            {
                "span_id": "child",
                "name": "child_span",
                "start_time": "2024-01-01T10:00:00.010Z",
                "end_time": "2024-01-01T10:00:00.098Z",
                "parent_span_id": "root",
            },
        ]
    }
    mock_fetch.return_value = trace_data

    result = analyze_critical_path("t1")

    assert "critical_path" in result
    path = result["critical_path"]
    assert len(path) == 2
    assert path[0]["span_id"] == "root"
    assert path[1]["span_id"] == "child"
    assert result["total_critical_duration_ms"] == 100.0


@patch("sre_agent.tools.analysis.trace.statistical_analysis.fetch_trace_data")
@patch("sre_agent.tools.analysis.trace.statistical_analysis.analyze_critical_path")
@patch("sre_agent.tools.analysis.trace.analysis.build_call_graph")
def test_perform_causal_analysis_success(
    mock_build_graph, mock_analyze_critical, mock_fetch
):
    # Baseline: Span A takes 10ms
    # Target: Span A takes 100ms
    baseline_data = {
        "spans": [
            {
                "span_id": "b1",
                "name": "spanA",
                "duration_ms": 10,
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-01T00:00:00.010Z",
            }
        ]
    }
    target_data = {
        "spans": [
            {
                "span_id": "t1",
                "name": "spanA",
                "duration_ms": 100,
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-01T00:00:00.100Z",
            }
        ]
    }
    mock_fetch.side_effect = [baseline_data, target_data]

    # Mock critical path logic
    mock_analyze_critical.return_value = {
        "critical_path": [{"span_id": "t1", "self_time_ms": 100}]
    }

    # Mock call graph logic
    mock_build_graph.return_value = {
        "span_tree": [{"span_id": "t1", "depth": 0, "children": []}]
    }

    result = perform_causal_analysis("base", "target")

    candidates = result["root_cause_candidates"]
    assert len(candidates) > 0
    top = candidates[0]
    assert top["span_name"] == "spanA"
    assert top["diff_ms"] == 90
    assert top["is_likely_root_cause"] is True


@patch("sre_agent.tools.analysis.trace.statistical_analysis._fetch_traces_parallel")
def test_analyze_trace_patterns_mocked_fetch(mock_fetch_parallel):
    t1 = {
        "trace_id": "t1",
        "duration_ms": 200,
        "spans": [{"name": "spanA", "duration_ms": 150}],
    }
    t2 = {
        "trace_id": "t2",
        "duration_ms": 200,
        "spans": [{"name": "spanA", "duration_ms": 155}],
    }
    t3 = {
        "trace_id": "t3",
        "duration_ms": 200,
        "spans": [{"name": "spanA", "duration_ms": 145}],
    }
    mock_fetch_parallel.return_value = [t1, t2, t3]

    result = analyze_trace_patterns(["t1", "t2", "t3"])

    # Based on error log, overall_trend is top level
    assert "overall_trend" in result

    patterns = result["patterns"]
    slowdown = next(
        (
            p
            for p in patterns["recurring_slowdowns"]
            if p["pattern_type"] == "recurring_slowdown"
        ),
        None,
    )
    assert slowdown is not None
    assert slowdown["span_name"] == "spanA"


@patch("sre_agent.tools.analysis.trace.statistical_analysis.compute_latency_statistics")
@patch("sre_agent.tools.analysis.trace.statistical_analysis.fetch_trace_data")
def test_detect_latency_anomalies_success(mock_fetch, mock_compute):
    baseline_stats = {
        "mean": 100,
        "stdev": 10,
        "per_span_stats": {"spanA": {"mean": 10, "stdev": 2, "p95": 14}},
    }
    mock_compute.return_value = baseline_stats

    # Target trace: spanA takes 60ms (anomaly vs 10ms +/- 4ms)
    # Must be > 50ms to be considered (threshold logic)
    target_data = {
        "duration_ms": 200,
        "spans": [
            {
                "name": "spanA",
                "duration_ms": 60,
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-01T00:00:00.060Z",
            }
        ],
    }
    mock_fetch.return_value = target_data

    result = detect_latency_anomalies(["b1"], "t1")

    assert result["is_anomaly"] is True
    spans = result["anomalous_spans"]
    assert len(spans) == 1
    assert spans[0]["span_name"] == "spanA"
    assert spans[0]["anomaly_type"] == "slow"
