"""Root Cause Analyzer - Consolidated agent for causality and impact analysis.

This agent combines the functionality of:
- causality_analyzer: Root cause determination and propagation analysis
- service_impact_analyzer: Blast radius and service-level impact assessment

This simplification reduces complexity while providing comprehensive
root cause analysis capabilities for SRE troubleshooting.
"""

from google.adk.agents import Agent

from ...tools.o11y_clients import fetch_trace, list_traces
from ...tools.statistical_analysis import (
    analyze_critical_path,
    compute_service_level_stats,
    perform_causal_analysis,
)
from ...tools.trace_analysis import extract_errors, find_structural_differences
from .prompt import ROOT_CAUSE_ANALYZER_PROMPT

root_cause_analyzer = Agent(
    name="root_cause_analyzer",
    model="gemini-2.5-pro",
    description=(
        "Root cause analysis agent that determines why issues occurred, "
        "traces causal chains, and assesses service-level blast radius."
    ),
    instruction=ROOT_CAUSE_ANALYZER_PROMPT,
    tools=[
        # Core trace retrieval
        fetch_trace,
        list_traces,
        # Causal analysis
        perform_causal_analysis,
        analyze_critical_path,
        find_structural_differences,
        # Impact analysis
        compute_service_level_stats,
        extract_errors,
    ],
)
