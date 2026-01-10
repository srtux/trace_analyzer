from unittest.mock import patch

import pytest

from sre_agent.tools.analysis.trace.comparison import (
    compare_span_timings,
    find_structural_differences,
)


@pytest.fixture
def mock_calculate_durations():
    with patch(
        "sre_agent.tools.analysis.trace.comparison.calculate_span_durations"
    ) as mock:
        yield mock


@pytest.fixture
def mock_build_call_graph():
    with patch("sre_agent.tools.analysis.trace.comparison.build_call_graph") as mock:
        yield mock


def test_compare_span_timings_n_plus_one(mock_calculate_durations):
    baseline = [{"name": "db_query", "duration_ms": 10}]
    target = []
    # 5 sequential calls
    for i in range(5):
        target.append(
            {
                "name": "db_query",
                "duration_ms": 20,
                "start_time": f"2024-01-01T00:00:{10 + i:02d}Z",
                "end_time": f"2024-01-01T00:00:{10 + i:02d}.020Z",
            }
        )
    target.append(
        {"name": "other", "duration_ms": 5, "start_time": "2024-01-01T00:00:00Z"}
    )

    mock_calculate_durations.side_effect = [baseline, target]

    result = compare_span_timings("base", "target", "p")

    patterns = result["patterns"]
    n_plus_one = next((p for p in patterns if p["type"] == "n_plus_one"), None)
    assert n_plus_one is not None
    assert n_plus_one["span_name"] == "db_query"
    assert n_plus_one["count"] >= 3


def test_compare_span_timings_serial_chain(mock_calculate_durations):
    # Setup target with serial chain
    # Ensure timestamps are simple and gaps match
    # A: 0 to 50ms
    # B: 50 to 100ms (0 gap)
    # C: 100 to 200ms (0 gap)
    target = [
        {
            "name": "A",
            "start_time": "2024-01-01T12:00:00.000Z",
            "end_time": "2024-01-01T12:00:00.050Z",
            "duration_ms": 50,
            "span_id": "1",
        },
        {
            "name": "B",
            "start_time": "2024-01-01T12:00:00.050Z",
            "end_time": "2024-01-01T12:00:00.100Z",
            "duration_ms": 50,
            "span_id": "2",
        },
        {
            "name": "C",
            "start_time": "2024-01-01T12:00:00.100Z",
            "end_time": "2024-01-01T12:00:00.200Z",
            "duration_ms": 100,
            "span_id": "3",
        },
    ]

    mock_calculate_durations.side_effect = [[], target]

    result = compare_span_timings("base", "target", "p")

    patterns = result["patterns"]
    serial = next((p for p in patterns if p["type"] == "serial_chain"), None)
    # If this fails, debugging is enabled:
    if not serial:
        print(f"Patterns found: {patterns}")

    assert serial is not None
    assert len(serial["span_names"]) == 3


def test_compare_span_timings_diffs(mock_calculate_durations):
    baseline = [
        {"name": "fast_func", "duration_ms": 10},
        {"name": "slow_func", "duration_ms": 100},
    ]
    target = [
        {"name": "fast_func", "duration_ms": 50},
        {"name": "slow_func", "duration_ms": 10},
    ]
    mock_calculate_durations.side_effect = [baseline, target]

    result = compare_span_timings("base", "target")

    slower = result["slower_spans"]
    assert len(slower) == 1
    assert slower[0]["span_name"] == "fast_func"
    assert slower[0]["diff_ms"] == 40

    faster = result["faster_spans"]
    assert len(faster) == 1
    assert faster[0]["span_name"] == "slow_func"
    assert faster[0]["diff_ms"] == -90


def test_find_structural_differences(mock_build_call_graph):
    baseline = {
        "span_names": ["root", "childA", "childB"],
        "max_depth": 2,
        "total_spans": 3,
    }
    target = {
        "span_names": ["root", "childA", "childC"],
        "max_depth": 3,
        "total_spans": 3,
    }
    mock_build_call_graph.side_effect = [baseline, target]

    result = find_structural_differences("base", "target")

    assert "childB" in result["missing_spans"]
    assert "childC" in result["new_spans"]
    assert result["depth_change"] == 1
