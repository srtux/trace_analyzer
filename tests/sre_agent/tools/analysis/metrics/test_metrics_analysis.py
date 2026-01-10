"""Tests for metrics analysis tools."""

from sre_agent.tools.analysis.metrics import (
    calculate_series_stats,
    compare_metric_windows,
    detect_metric_anomalies,
)


def test_calculate_series_stats_basic():
    data = [1.0, 2.0, 3.0, 4.0, 5.0]
    stats = calculate_series_stats(data)

    assert stats["count"] == 5.0
    assert stats["mean"] == 3.0
    assert stats["median"] == 3.0
    assert stats["min"] == 1.0
    assert stats["max"] == 5.0
    # population stdev of 1,2,3,4,5 is sqrt(2), sample stdev is sqrt(2.5) ~ 1.58
    assert abs(stats["stdev"] - 1.58) < 0.01


def test_calculate_series_stats_empty():
    assert calculate_series_stats([]) == {}


def test_detect_metric_anomalies_basic():
    # Mean=5, Stdev=0. (all 5s)
    # Add an anomaly: 100
    data = [5.0] * 10 + [100.0]

    # 5.0 * 10 = 50. + 100 = 150. / 11 ~= 13.6
    # This might skewer stdev.

    result = detect_metric_anomalies(data, threshold_sigma=2.0)
    assert result["is_anomaly_detected"] is True
    assert result["anomalies_count"] == 1
    assert result["anomalies"][0]["value"] == 100.0


def test_detect_metric_anomalies_dicts():
    data = [{"v": 10}, {"v": 10}, {"v": 500}]
    result = detect_metric_anomalies(data, value_key="v", threshold_sigma=1.0)
    assert result["is_anomaly_detected"] is True
    assert result["anomalies"][0]["value"] == 500.0
    assert result["anomalies"][0]["original_data"] == {"v": 500}


def test_compare_metric_windows_shift():
    base = [10.0] * 10
    target = [20.0] * 10

    result = compare_metric_windows(base, target)
    assert result["comparison"]["is_significant_shift"] is True
    assert result["comparison"]["mean_shift"] == 10.0
    assert result["comparison"]["mean_shift_pct"] == 100.0


def test_compare_metric_windows_stable():
    base = [10.0] * 10
    target = [10.1] * 10

    result = compare_metric_windows(base, target)
    assert result["comparison"]["is_significant_shift"] is False
    assert result["comparison"]["mean_shift_pct"] < 10.0


def test_calculate_series_stats_single_point():
    data = [42.0]
    stats = calculate_series_stats(data)
    assert stats["count"] == 1.0
    assert stats["stdev"] == 0.0
    assert stats["mean"] == 42.0


def test_detect_metric_anomalies_no_anomalies():
    # Normal distributionish data
    data = [10.0, 11.0, 9.0, 10.5, 9.5]
    result = detect_metric_anomalies(data, threshold_sigma=3.0)
    assert result["is_anomaly_detected"] is False
    assert len(result["anomalies"]) == 0


def test_detect_metric_anomalies_zero_variance():
    # All same values
    data = [10.0] * 5
    result = detect_metric_anomalies(data)
    assert result["is_anomaly_detected"] is False
    assert result["params"]["stdev"] == 0.0
