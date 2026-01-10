"""Anomaly detection for metrics data."""

import logging
from typing import Any

from .statistics import calculate_series_stats
from ...common.decorators import adk_tool

logger = logging.getLogger(__name__)

@adk_tool
def detect_metric_anomalies(
    data_points: list[float] | list[dict[str, Any]],
    threshold_sigma: float = 3.0,
    value_key: str = "value",
) -> dict[str, Any]:
    """
    Detects anomalies in a series of data points using Z-score.

    Args:
        data_points: List of values or dicts containing values.
                     If dicts, 'value_key' is used to extract the number.
        threshold_sigma: Z-score threshold for anomaly detection (default 3.0).
        value_key: Key to look for if input is list of dicts.

    Returns:
        Dictionary with anomaly analysis.
    """
    values = []
    original_data_map = {} # Map index to original data for reconstruction

    for i, item in enumerate(data_points):
        val = None
        if isinstance(item, (int, float)):
            val = float(item)
        elif isinstance(item, dict):
            val = float(item.get(value_key, 0.0))
        
        if val is not None:
            values.append(val)
            original_data_map[len(values) - 1] = item

    if not values:
        return {"error": "No valid data points found"}

    stats = calculate_series_stats(values)
    mean = stats["mean"]
    stdev = stats["stdev"]

    anomalies = []
    
    if stdev > 0:
        for i, val in enumerate(values):
            z_score = (val - mean) / stdev
            if abs(z_score) > threshold_sigma:
                anomalies.append({
                    "index": i,
                    "value": val,
                    "z_score": round(z_score, 2),
                    "original_data": original_data_map.get(i),
                    "type": "high" if z_score > 0 else "low"
                })
    
    return {
        "is_anomaly_detected": len(anomalies) > 0,
        "anomalies_count": len(anomalies),
        "total_points": len(values),
        "params": {
            "threshold_sigma": threshold_sigma,
            "mean": round(mean, 2),
            "stdev": round(stdev, 2)
        },
        "anomalies": anomalies
    }

@adk_tool
def compare_metric_windows(
    baseline_points: list[float],
    target_points: list[float],
) -> dict[str, Any]:
    """
    Compares two windows of metric data to detect shifts.

    Args:
        baseline_points: List of baseline values.
        target_points: List of target values to compare.

    Returns:
        Comparison result stats.
    """
    if not baseline_points or not target_points:
        return {"error": "Missing data for comparison"}

    base_stats = calculate_series_stats(baseline_points)
    target_stats = calculate_series_stats(target_points)

    mean_shift = target_stats["mean"] - base_stats["mean"]
    if base_stats["mean"] != 0:
        mean_shift_pct = (mean_shift / base_stats["mean"]) * 100
    else:
        mean_shift_pct = 100.0 if mean_shift > 0 else 0.0

    return {
        "baseline_stats": base_stats,
        "target_stats": target_stats,
        "comparison": {
            "mean_shift": round(mean_shift, 4),
            "mean_shift_pct": round(mean_shift_pct, 2),
            "is_significant_shift": abs(mean_shift_pct) > 10.0 # 10% arbitrary threshold
        }
    }
