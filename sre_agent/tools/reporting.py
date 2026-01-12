"""Tool for synthesizing investigation reports."""

from typing import Any

from google.adk.tools import ToolContext  # type: ignore[attr-defined]

from .common import adk_tool


@adk_tool
async def synthesize_report(
    root_cause_analysis: dict[str, Any],
    triage_results: dict[str, Any],
    aggregate_results: dict[str, Any] | None = None,
    log_analysis: dict[str, Any] | None = None,
    tool_context: ToolContext | None = None,
) -> str:
    """Synthesize a structured Root Cause Hypothesis report.

    Args:
        root_cause_analysis: Output from run_deep_dive_analysis.
        triage_results: Output from run_triage_analysis.
        aggregate_results: Output from run_aggregate_analysis (optional).
        log_analysis: Output from run_log_pattern_analysis (optional).
        tool_context: Tool context.

    Returns:
        Markdown-formatted investigation report.
    """
    # This is a helper tool to structure the final output.
    # In a real agent, the LLM might do this naturally, but having a structured
    # tool ensures consistent formatting.

    report = ["# Root Cause Investigation Report\n"]

    # 1. Executive Summary
    report.append("## Executive Summary")
    # Extract likely root cause from deep dive
    causality = (
        root_cause_analysis.get("results", {})
        .get("causality", {})
        .get("result", "Analysis Inconclusive")
    )
    report.append(f"{causality}\n")

    # 2. Evidence
    report.append("## Evidence")

    # Change Detection
    change_detective = (
        root_cause_analysis.get("results", {})
        .get("change_detective", {})
        .get("result", "No change detection data")
    )
    report.append(f"### Change Correlation\n{change_detective}\n")

    # 3. Trace Analysis
    report.append("## Trace Forensics")
    if aggregate_results:
        report.append(
            f"### Aggregate Patterns\n{aggregate_results.get('result', 'No aggregate data')}\n"
        )

    for name, result in triage_results.get("results", {}).items():
        if result.get("status") == "success":
            report.append(f"### {name.title()} Specialist\n{result.get('result')}\n")

    # 4. Log Analysis
    if log_analysis:
        report.append(
            f"## Log Patterns\n{log_analysis.get('result', 'No log analysis data')}\n"
        )

    # 5. Service Impact
    impact = (
        root_cause_analysis.get("results", {})
        .get("service_impact", {})
        .get("result", "Unknown Impact")
    )
    report.append(f"## Impact Assessment\n{impact}\n")

    return "\n".join(report)
