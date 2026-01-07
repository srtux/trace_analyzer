
import pytest
from trace_analyzer.agent import stage1_triage_squad, stage2_deep_dive_squad, root_agent

def test_stage1_squad_has_correct_agents():
    """Verify Stage 1 has 4 independent agents."""
    assert len(stage1_triage_squad.sub_agents) == 4
    agent_names = [a.name for a in stage1_triage_squad.sub_agents]
    assert "latency_analyzer" in agent_names
    assert "error_analyzer" in agent_names
    assert "structure_analyzer" in agent_names
    assert "statistics_analyzer" in agent_names

def test_stage2_squad_has_correct_agents():
    """Verify Stage 2 has 2 dependent agents."""
    assert len(stage2_deep_dive_squad.sub_agents) == 2
    agent_names = [a.name for a in stage2_deep_dive_squad.sub_agents]
    assert "causality_analyzer" in agent_names
    assert "service_impact_analyzer" in agent_names

def test_root_agent_has_new_tools():
    """Verify root agent has access to all new tools."""
    tool_names = [t.__name__ if hasattr(t, '__name__') else str(t) for t in root_agent.tools]
    
    # Check for the two-stage runner
    assert "run_two_stage_analysis" in tool_names
    
    # Check for external integrations
    assert "query_logs_for_trace" in tool_names or "list_log_entries" in tool_names
    assert "query_metrics_for_timerange" in tool_names or "list_time_series" in tool_names
    assert "query_error_events" in tool_names or "list_error_events" in tool_names
    
    # Check for selection tools
    assert "select_traces_from_error_reports" in tool_names
    assert "select_traces_from_monitoring_alerts" in tool_names
    assert "select_traces_from_statistical_outliers" in tool_names
    assert "select_traces_manually" in tool_names
