"""Statistical analysis for time series data."""

import statistics
from typing import Any

from ...common.decorators import adk_tool

@adk_tool
def calculate_series_stats(points: list[float]) -> dict[str, float]:
    """
    Calculates statistical metrics for a list of data points.

    Args:
        points: List of numerical values.

    Returns:
        Dictionary containing statistical metrics.
    """
    if not points:
        return {}

    points_sorted = sorted(points)
    count = len(points_sorted)

    stats = {
        "count": float(count),
        "min": points_sorted[0],
        "max": points_sorted[-1],
        "mean": statistics.mean(points_sorted),
        "median": statistics.median(points_sorted),
    }

    if count > 1:
        stats["stdev"] = statistics.stdev(points_sorted)
        stats["variance"] = statistics.variance(points_sorted)
        stats["p90"] = points_sorted[int(count * 0.9)]
        stats["p95"] = points_sorted[int(count * 0.95)]
        stats["p99"] = points_sorted[int(count * 0.99)]
    else:
        stats["stdev"] = 0.0
        stats["variance"] = 0.0
        stats["p90"] = points_sorted[0]
        stats["p95"] = points_sorted[0]
        stats["p99"] = points_sorted[0]

    return stats
