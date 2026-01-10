import json
from unittest.mock import patch

import pytest

from sre_agent.tools.analysis.trace.comparison import compare_span_timings
from sre_agent.tools.analysis.trace.statistical_analysis import analyze_trace_patterns
from tests.fixtures.synthetic_otel_data import OtelSpanGenerator, TraceGenerator


def convert_trace_to_json(trace_spans):
    """Helper to convert list of spans to the JSON format expected by tools."""
    # Group by trace_id (should be unique for single trace)
    if not trace_spans:
        return "{}"

    trace_id = trace_spans[0].get("trace_id", "unknown")

    # Convert spans to the simplified format used in analysis tools if needed,
    # or keep as proper OTel format depending on what the tool expects.
    # Looking at the original static files, it seems to expect a dict with "spans" key.

    # Calculate duration correctly
    start_times = [s.get("start_time") for s in trace_spans if "start_time" in s]
    end_times = [s.get("end_time") for s in trace_spans if "end_time" in s]

    duration_ms = 0.0
    if start_times and end_times:
        try:
            # Simple string comparison isn't enough for time diff, but
            # for now let's just use the root span's duration if available,
            # or roughly estimate if we really parsed them.
            # Since importing datetime parsing here might be overkill if not already imported,
            # let's look for known fields.

            # Better approach: Iterate to find the root span (no parent) and use its duration if present
            root_span = next(
                (s for s in trace_spans if not s.get("parent_span_id")), None
            )
            if root_span:
                # duration_nano is strictly available in our generator
                duration_ms = root_span.get("duration_nano", 0) / 1e6
        except Exception:
            pass

    return json.dumps(
        {
            "trace_id": trace_id,
            "project_id": "test-project",
            "spans": trace_spans,
            "duration_ms": duration_ms,
        }
    )


@pytest.fixture
def good_trace_json():
    generator = TraceGenerator()
    # Create a nice fast trace
    spans = generator.create_multi_service_trace(
        services=[
            "ProcessRequest",
            "AuthenticateUser",
            "FetchUserProfile",
            "RenderResponse",
        ],
        latency_strategy="normal",
    )
    # Fix names to match test expectations if they rely on specific names
    # Original: ProcessRequest, AuthenticateUser, FetchUserProfile, RenderResponse
    # We can rename them to match the test logic expectation
    for i, name in enumerate(
        ["ProcessRequest", "AuthenticateUser", "FetchUserProfile", "RenderResponse"]
    ):
        if i < len(spans):
            spans[i]["name"] = name

    return convert_trace_to_json(spans)


@pytest.fixture
def bad_trace_json():
    TraceGenerator()
    trace_id = "bad_trace_001"

    # We need to simulate N+1 problem: Root -> Multiple redundant DB calls
    # Original bad_trace.json had: ProcessRequest -> AuthenticateUser, FetchItem x4, ProcessItems (error)

    spans = []
    root_gen = OtelSpanGenerator(trace_id=trace_id)
    root = root_gen.create_span(name="ProcessRequest", duration_ms=1500.0)
    spans.append(root)

    # N+1 calls
    # N+1 calls - make them sequential
    from datetime import timedelta

    current_time = root_gen.base_time + timedelta(milliseconds=10)

    for _i in range(4):
        child_gen = OtelSpanGenerator(
            trace_id=trace_id, parent_span_id=root["span_id"], base_time=current_time
        )
        child = child_gen.create_span(name="FetchItem", duration_ms=100.0)
        spans.append(child)
        current_time = current_time + timedelta(
            milliseconds=110
        )  # 100ms duration + 10ms gap

    return convert_trace_to_json(spans)


@pytest.fixture
def mock_fetch_trace():
    """
    Mock fetch_trace_data to return the input trace_id (as dict) as the result.
    This is necessary because the tests pass the full JSON content as the trace_id.
    """
    import json

    with (
        patch("sre_agent.tools.analysis.trace.analysis.fetch_trace_data") as mock_a,
        patch(
            "sre_agent.tools.analysis.trace.statistical_analysis.fetch_trace_data"
        ) as mock_b,
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
    assert root_diff["diff_ms"] > 500  # 1500ms vs normal


def test_analyze_trace_patterns_e2e(bad_trace_json, mock_fetch_trace):
    """
    Test pattern analysis on a set of bad traces.
    """
    # Simulate multiple bad traces to trigger pattern detection
    traces = [bad_trace_json, bad_trace_json, bad_trace_json]

    result = analyze_trace_patterns(traces)

    patterns = result.get("patterns", {})

    recurring = patterns.get("recurring_slowdowns", [])
    # root_span_bad is 1500ms > 100ms threshold
    root_pattern = next(
        (p for p in recurring if p["span_name"] == "ProcessRequest"), None
    )

    assert root_pattern is not None
    assert root_pattern["avg_duration_ms"] == 1500.0
    assert root_pattern["consistency"] == 100.0  # Identical traces = 100% consistent
