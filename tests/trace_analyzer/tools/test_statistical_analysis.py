
import json
import pytest
from trace_analyzer.tools.statistical_analysis import (
    perform_causal_analysis,
    compute_latency_statistics,
    detect_latency_anomalies
)

@pytest.fixture
def baseline_trace():
    return json.dumps({
        "trace_id": "baseline",
        "spans": [
            {
                "span_id": "root", "name": "root", 
                "start_time": "2020-01-01T00:00:00.000Z", 
                "end_time":   "2020-01-01T00:00:00.100Z", # 100ms
                "parent_span_id": None
            },
            {
                "span_id": "child", "name": "child",
                "start_time": "2020-01-01T00:00:00.010Z",
                "end_time":   "2020-01-01T00:00:00.060Z", # 50ms
                "parent_span_id": "root"
            }
        ]
    })

@pytest.fixture
def slow_target_trace():
    return json.dumps({
        "trace_id": "target",
        "spans": [
            {
                "span_id": "root", "name": "root", # 200ms (100ms slower)
                "start_time": "2020-01-01T00:00:00.000Z", 
                "end_time":   "2020-01-01T00:00:00.200Z", 
                "parent_span_id": None
            },
            {
                "span_id": "child", "name": "child", # 150ms (100ms slower) -> Root cause likely here
                "start_time": "2020-01-01T00:00:00.010Z",
                "end_time":   "2020-01-01T00:00:00.160Z", 
                "parent_span_id": "root"
            }
        ]
    })

def test_perform_causal_analysis(baseline_trace, slow_target_trace):
    """Test causal analysis using string inputs (integration checks build_call_graph fix)."""
    analysis = perform_causal_analysis(baseline_trace, slow_target_trace)
    
    assert "root_cause_candidates" in analysis
    candidates = analysis["root_cause_candidates"]
    assert len(candidates) > 0
    # Child is likely identified as root cause because it slowed down and parent slowed down too
    # Logic: child slowed by 100ms (50->150), root slowed by 100ms (100->200).
    # Since child is independent (leaf), it's a candidate.
    
    top_cause = candidates[0]
    assert top_cause["span_name"] == "child"
    assert top_cause["is_root_cause"] is True

def test_compute_latency_statistics(baseline_trace):
    """Test latency statistics computation."""
    # Pass a list of trace strings
    stats = compute_latency_statistics([baseline_trace, baseline_trace])
    
    assert "per_span_stats" in stats
    root_stats = stats["per_span_stats"]["root"]
    assert root_stats["count"] == 2
    assert root_stats["mean"] == 100.0
    assert root_stats["min"] == 100.0
    assert root_stats["max"] == 100.0

def test_detect_latency_anomalies(baseline_trace, slow_target_trace):
    """Test anomaly detection logic."""
    # We need multiple baseline traces to get a std_dev, or at least one (std_dev will be 0->1)
    # If we pass 5 identical traces, std_dev = 0, so it defaults to 1.
    # Mean = 100ms.
    # Target root = 200ms. Z-score = (200 - 100) / 1 = 100. Very high.
    
    result = detect_latency_anomalies([baseline_trace] * 5, slow_target_trace)
    
    assert len(result["anomalous_spans"]) > 0
    anomalies = {a["span_name"]: a for a in result["anomalous_spans"]}
    
    assert "root" in anomalies
    assert anomalies["root"]["anomaly_type"] == "slow"
    assert "child" in anomalies
    assert anomalies["child"]["anomaly_type"] == "slow"
