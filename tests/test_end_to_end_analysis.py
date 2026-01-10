import os
from unittest.mock import patch

import pytest

from gcp_observability.tools.analysis.trace.statistical_analysis import analyze_trace_patterns
from gcp_observability.tools.analysis.trace.comparison import compare_span_timings

# Load fake data
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def load_trace(filename):
    with open(os.path.join(DATA_DIR, filename)) as f:
        return f.read()


@pytest.fixture
def good_trace_json():
    return load_trace("good_trace.json")


@pytest.fixture
def bad_trace_json():
    return load_trace("bad_trace.json")


@pytest.fixture
def mock_fetch_trace():
    """
    Mock fetch_trace_data to return the input trace_id (as dict) as the result.
    This is necessary because the tests pass the full JSON content as the trace_id.
    """
    import json
    with (
        patch("gcp_observability.tools.analysis.trace.analysis.fetch_trace_data") as mock_a,
        patch("gcp_observability.tools.analysis.trace.statistical_analysis.fetch_trace_data") as mock_b,
    ):

        def side_effect(trace_id, project_id=None):
            if isinstance(trace_id, str) and trace_id.strip().startswith("{"):
                return json.loads(trace_id)
            return trace_id

        mock_a.side_effect = side_effect
        mock_b.side_effect = side_effect
        yield


def test_compare_span_timings_e2e(good_trace_json, bad_trace_json, mock_fetch_trace):
    """
    Test comparison between a good baseline and a bad target trace.
    Should detect N+1 pattern and slowness.
    """
    result = compare_span_timings(good_trace_json, bad_trace_json)

    # Check N+1 detection
    patterns = result.get("patterns", [])
    n_plus_one = next((p for p in patterns if p["type"] == "n_plus_one"), None)
    assert n_plus_one is not None
    assert n_plus_one["span_name"] == "FetchItem"
    assert n_plus_one["count"] >= 4  # We added 4 sequential calls

    # Check timing comparison
    # Root span should be slower
    slower_spans = result.get("slower_spans", [])
    root_diff = next(
        (s for s in slower_spans if s["span_name"] == "ProcessRequest"), None
    )

    # Note: fake data names must match for comparison.
    # good_trace has "ProcessRequest", bad_trace has "ProcessRequest"
    assert root_diff is not None
    assert root_diff["diff_ms"] > 1000  # 1500ms vs 150ms


def test_analyze_trace_patterns_e2e(bad_trace_json, mock_fetch_trace):
    """
    Test pattern analysis on a set of bad traces.
    """
    # Simulate multiple bad traces to trigger pattern detection
    traces = [bad_trace_json, bad_trace_json, bad_trace_json]

    result = analyze_trace_patterns(traces)

    patterns = result.get("patterns", {})

    # improved: analyze_trace_patterns logic requires variances for some patterns,
    # but identical traces might trigger "recurring_slowdown" if duration is high and stable.

    recurring = patterns.get("recurring_slowdowns", [])
    # root_span_bad is 1500ms > 100ms threshold
    root_pattern = next(
        (p for p in recurring if p["span_name"] == "ProcessRequest"), None
    )

    assert root_pattern is not None
    assert root_pattern["avg_duration_ms"] == 1500.0
    assert root_pattern["consistency"] == 100.0  # Identical traces = 100% consistent
