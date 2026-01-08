"""Trace Investigator - Consolidated agent for comprehensive trace analysis.

This agent combines the functionality of:
- latency_analyzer: Span timing comparison
- error_analyzer: Error detection and comparison
- structure_analyzer: Call graph topology changes
- statistics_analyzer: Statistical distribution analysis

This simplification reduces the number of parallel agents while maintaining
full analysis capabilities for SRE troubleshooting.
"""

from google.adk.agents import Agent

from ...tools.o11y_clients import fetch_trace, list_traces
from ...tools.statistical_analysis import (
    analyze_critical_path,
    compute_latency_statistics,
    detect_latency_anomalies,
)
from ...tools.trace_analysis import (
    build_call_graph,
    compare_span_timings,
    extract_errors,
    find_structural_differences,
)
from .prompt import TRACE_INVESTIGATOR_PROMPT

trace_investigator = Agent(
    name="trace_investigator",
    model="gemini-2.5-pro",
    description=(
        "Comprehensive trace analysis agent that examines latency, errors, "
        "structure, and statistical patterns between baseline and target traces."
    ),
    instruction=TRACE_INVESTIGATOR_PROMPT,
    tools=[
        # Core trace retrieval
        fetch_trace,
        list_traces,
        # Latency analysis
        compare_span_timings,
        # Error analysis
        extract_errors,
        # Structure analysis
        build_call_graph,
        find_structural_differences,
        # Statistical analysis
        compute_latency_statistics,
        detect_latency_anomalies,
        analyze_critical_path,
    ],
)
