import json
from unittest.mock import patch

from sre_agent.tools.analysis.trace.comparison import compare_span_timings


def test_compare_span_timings_n_plus_one_detection():
    """Test that N+1 query patterns are detected."""
    with patch(
        "sre_agent.tools.analysis.trace.analysis.fetch_trace_data",
        side_effect=lambda tid, pid: json.loads(tid) if isinstance(tid, str) else tid,
    ):
        baseline = {
            "trace_id": "base",
            "spans": [
                {
                    "span_id": "r",
                    "name": "root",
                    "start_time": "2023-01-01T00:00:00Z",
                    "end_time": "2023-01-01T00:00:01Z",
                }
            ],
        }

        # Construct a trace with N+1 pattern: 5 sequential calls to "db_query"
        spans = [
            {
                "span_id": "root",
                "name": "root",
                "start_time": "2023-01-01T00:00:00Z",
                "end_time": "2023-01-01T00:00:05Z",
            }
        ]

        for i in range(5):
            spans.append(
                {
                    "span_id": f"q{i}",
                    "name": "db_query",
                    # 100ms duration, sequential
                    # q0: 0.1 - 0.2
                    # q1: 0.2 - 0.3
                    "start_time": f"2023-01-01T00:00:00.{i + 1}00Z",
                    "end_time": f"2023-01-01T00:00:00.{i + 2}00Z",
                    "parent_span_id": "root",
                }
            )

        target = {"trace_id": "target", "spans": spans}

        result = compare_span_timings(json.dumps(baseline), json.dumps(target))

        assert "patterns" in result
        patterns = result["patterns"]
        assert len(patterns) >= 1

        n_plus_one = next((p for p in patterns if p["type"] == "n_plus_one"), None)
        assert n_plus_one is not None
        assert n_plus_one["span_name"] == "db_query"
        assert n_plus_one["count"] == 5
        # 100ms * 5 = 500ms
        assert n_plus_one["total_duration_ms"] == 500.0


def test_compare_span_timings_serial_chain_detection():
    """Test that serial chain patterns (waterfalls) are detected."""
    with patch(
        "sre_agent.tools.analysis.trace.analysis.fetch_trace_data",
        side_effect=lambda tid, pid: json.loads(tid) if isinstance(tid, str) else tid,
    ):
        baseline = {
            "trace_id": "base",
            "spans": [
                {
                    "span_id": "r",
                    "name": "root",
                    "start_time": "2023-01-01T00:00:00Z",
                    "end_time": "2023-01-01T00:00:05Z",
                }
            ],
        }

        # Construct a serial chain of 4 different spans, each starting exactly when the previous ends
        spans = [
            {
                "span_id": "root",
                "name": "root",
                "start_time": "2023-01-01T00:00:00Z",
                "end_time": "2023-01-01T00:00:05Z",
            }
        ]

        chain_names = ["auth", "get_user", "get_permissions", "audit_log"]

        for i, name in enumerate(chain_names):
            spans.append(
                {
                    "span_id": f"s{i}",
                    "name": name,
                    # Each is 200ms, starting immediately after previous
                    "start_time": f"2023-01-01T00:00:00.{i * 2}00Z",
                    "end_time": f"2023-01-01T00:00:00.{(i + 1) * 2}00Z",
                    "parent_span_id": "root",
                }
            )

        target = {"trace_id": "target", "spans": spans}

        result = compare_span_timings(json.dumps(baseline), json.dumps(target))

        assert "patterns" in result
        patterns = result["patterns"]
        serial_chain = next((p for p in patterns if p["type"] == "serial_chain"), None)

        assert serial_chain is not None
        assert serial_chain["count"] == 4
        # 200ms * 4 = 800ms
        assert serial_chain["total_duration_ms"] == 800.0
        assert "could potentially be parallelized" in serial_chain["description"]
