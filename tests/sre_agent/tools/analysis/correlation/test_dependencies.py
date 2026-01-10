"""Tests for service dependency analysis tools.

These tests verify the functionality of tools that analyze service dependencies,
upstream/downstream impact, and detect architectural issues like circular dependencies.
"""

import json
import pytest

from sre_agent.tools.analysis.correlation.dependencies import (
    build_service_dependency_graph,
    analyze_upstream_downstream_impact,
    detect_circular_dependencies,
    find_hidden_dependencies,
)


class TestBuildServiceDependencyGraph:
    """Tests for build_service_dependency_graph tool."""

    def test_basic_dependency_graph_generation(self):
        """Test basic dependency graph SQL generation."""
        result = build_service_dependency_graph(
            dataset_id="project.telemetry",
        )

        parsed = json.loads(result)
        assert parsed["analysis_type"] == "service_dependency_graph"
        assert "dependency_graph_sql" in parsed
        assert "topology_sql" in parsed

    def test_dependency_sql_uses_client_spans(self):
        """Test that SQL focuses on CLIENT spans for dependencies."""
        result = build_service_dependency_graph(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        sql = parsed["dependency_graph_sql"]

        # Should filter for CLIENT spans (kind = 3)
        assert "kind = 3" in sql or "CLIENT" in sql

    def test_dependency_sql_extracts_peer_service(self):
        """Test that SQL extracts target service from peer attributes."""
        result = build_service_dependency_graph(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        sql = parsed["dependency_graph_sql"]

        # Should look for peer.service or similar attributes
        assert "peer.service" in sql or "net.peer.name" in sql

    def test_custom_time_window(self):
        """Test that custom time window is used."""
        result = build_service_dependency_graph(
            dataset_id="proj.ds",
            time_window_hours=48,
        )

        parsed = json.loads(result)
        sql = parsed["dependency_graph_sql"]

        assert "48" in sql

    def test_custom_min_call_count(self):
        """Test that custom minimum call count is used."""
        result = build_service_dependency_graph(
            dataset_id="proj.ds",
            min_call_count=100,
        )

        parsed = json.loads(result)
        sql = parsed["dependency_graph_sql"]

        assert "100" in sql

    def test_includes_topology_sql(self):
        """Test that topology SQL is included."""
        result = build_service_dependency_graph(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "topology_sql" in parsed

        topology_sql = parsed["topology_sql"]
        assert "SELECT" in topology_sql

    def test_includes_output_format_documentation(self):
        """Test that output format is documented."""
        result = build_service_dependency_graph(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "output_format" in parsed

        output_format = parsed["output_format"]
        assert "nodes" in output_format
        assert "edges" in output_format

    def test_includes_topology_roles(self):
        """Test that topology roles are documented."""
        result = build_service_dependency_graph(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "topology_roles" in parsed

        roles = parsed["topology_roles"]
        assert "ENTRY_POINT" in roles
        assert "INTERMEDIATE" in roles
        assert "LEAF" in roles

    def test_includes_metrics_explanation(self):
        """Test that metrics are explained."""
        result = build_service_dependency_graph(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "metrics_explained" in parsed


class TestAnalyzeUpstreamDownstreamImpact:
    """Tests for analyze_upstream_downstream_impact tool."""

    def test_basic_impact_analysis(self):
        """Test basic upstream/downstream impact analysis."""
        result = analyze_upstream_downstream_impact(
            dataset_id="project.telemetry",
            service_name="my-service",
        )

        parsed = json.loads(result)
        assert parsed["analysis_type"] == "upstream_downstream_impact"
        assert parsed["target_service"] == "my-service"
        assert "sql_query" in parsed

    def test_sql_includes_service_filter(self):
        """Test that SQL filters by target service."""
        result = analyze_upstream_downstream_impact(
            dataset_id="proj.ds",
            service_name="target-service",
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        assert "target-service" in sql

    def test_sql_finds_upstream_services(self):
        """Test that SQL finds upstream (caller) services."""
        result = analyze_upstream_downstream_impact(
            dataset_id="proj.ds",
            service_name="svc",
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        # Should have logic for finding callers
        assert "UPSTREAM" in sql or "upstream" in sql.lower() or "CALLER" in sql

    def test_sql_finds_downstream_services(self):
        """Test that SQL finds downstream (callee) services."""
        result = analyze_upstream_downstream_impact(
            dataset_id="proj.ds",
            service_name="svc",
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        # Should have logic for finding callees
        assert "DOWNSTREAM" in sql or "downstream" in sql.lower() or "DEPENDENCY" in sql

    def test_custom_time_window(self):
        """Test that custom time window is used."""
        result = analyze_upstream_downstream_impact(
            dataset_id="proj.ds",
            service_name="svc",
            time_window_hours=72,
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        assert "72" in sql

    def test_custom_depth(self):
        """Test that custom depth is used."""
        result = analyze_upstream_downstream_impact(
            dataset_id="proj.ds",
            service_name="svc",
            depth=5,
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        assert "5" in sql

    def test_includes_directions_explanation(self):
        """Test that directions are explained."""
        result = analyze_upstream_downstream_impact(
            dataset_id="proj.ds",
            service_name="svc",
        )

        parsed = json.loads(result)
        assert "directions_explained" in parsed

        directions = parsed["directions_explained"]
        assert "UPSTREAM" in directions
        assert "DOWNSTREAM" in directions

    def test_includes_relationships_explanation(self):
        """Test that relationship types are explained."""
        result = analyze_upstream_downstream_impact(
            dataset_id="proj.ds",
            service_name="svc",
        )

        parsed = json.loads(result)
        assert "relationships" in parsed

    def test_includes_incident_response_usage(self):
        """Test that incident response usage guide is included."""
        result = analyze_upstream_downstream_impact(
            dataset_id="proj.ds",
            service_name="svc",
        )

        parsed = json.loads(result)
        assert "incident_response_usage" in parsed


class TestDetectCircularDependencies:
    """Tests for detect_circular_dependencies tool."""

    def test_basic_cycle_detection(self):
        """Test basic circular dependency detection."""
        result = detect_circular_dependencies(
            dataset_id="project.telemetry",
        )

        parsed = json.loads(result)
        assert parsed["analysis_type"] == "circular_dependency_detection"
        assert "sql_query" in parsed

    def test_sql_detects_length_2_cycles(self):
        """Test that SQL can detect A -> B -> A cycles."""
        result = detect_circular_dependencies(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        # Should have logic for detecting 2-hop cycles
        assert "cycles_2" in sql.lower() or "cycle_length" in sql.lower()

    def test_sql_detects_length_3_cycles(self):
        """Test that SQL can detect A -> B -> C -> A cycles."""
        result = detect_circular_dependencies(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        # Should have logic for detecting 3-hop cycles
        assert "cycles_3" in sql.lower() or "3" in sql

    def test_custom_time_window(self):
        """Test that custom time window is used."""
        result = detect_circular_dependencies(
            dataset_id="proj.ds",
            time_window_hours=48,
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        assert "48" in sql

    def test_includes_problem_explanation(self):
        """Test that why cycles are problematic is explained."""
        result = detect_circular_dependencies(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "why_cycles_are_problematic" in parsed

        problems = parsed["why_cycles_are_problematic"]
        # Should mention various issues with circular dependencies
        assert len(problems) > 0

    def test_includes_common_patterns(self):
        """Test that common cycle patterns are documented."""
        result = detect_circular_dependencies(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "common_cycle_patterns" in parsed

    def test_includes_resolution_strategies(self):
        """Test that resolution strategies are included."""
        result = detect_circular_dependencies(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "resolution_strategies" in parsed

        strategies = parsed["resolution_strategies"]
        assert len(strategies) > 0


class TestFindHiddenDependencies:
    """Tests for find_hidden_dependencies tool."""

    def test_basic_hidden_dependency_detection(self):
        """Test basic hidden dependency detection."""
        result = find_hidden_dependencies(
            dataset_id="project.telemetry",
        )

        parsed = json.loads(result)
        assert parsed["analysis_type"] == "hidden_dependencies"
        assert "sql_query" in parsed

    def test_sql_analyzes_client_spans(self):
        """Test that SQL analyzes CLIENT spans."""
        result = find_hidden_dependencies(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        assert "kind = 3" in sql or "CLIENT" in sql

    def test_sql_extracts_database_dependencies(self):
        """Test that SQL extracts database dependencies."""
        result = find_hidden_dependencies(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        assert "db.system" in sql or "DATABASE" in sql

    def test_sql_extracts_http_dependencies(self):
        """Test that SQL extracts HTTP dependencies."""
        result = find_hidden_dependencies(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        assert "http" in sql.lower()

    def test_custom_time_window(self):
        """Test that custom time window is used."""
        result = find_hidden_dependencies(
            dataset_id="proj.ds",
            time_window_hours=72,
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        assert "72" in sql

    def test_custom_min_call_count(self):
        """Test that custom minimum call count is used."""
        result = find_hidden_dependencies(
            dataset_id="proj.ds",
            min_call_count=50,
        )

        parsed = json.loads(result)
        sql = parsed["sql_query"]

        assert "50" in sql

    def test_includes_dependency_types(self):
        """Test that dependency types are documented."""
        result = find_hidden_dependencies(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "dependency_types" in parsed

        types = parsed["dependency_types"]
        assert "DATABASE" in types
        assert "HTTP_EXTERNAL" in types or len(types) > 2

    def test_includes_priority_explanation(self):
        """Test that documentation priority is explained."""
        result = find_hidden_dependencies(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "documentation_priority_meaning" in parsed

    def test_includes_common_issues(self):
        """Test that common hidden dependency issues are documented."""
        result = find_hidden_dependencies(
            dataset_id="proj.ds",
        )

        parsed = json.loads(result)
        assert "common_hidden_dependency_issues" in parsed


class TestDependencyToolsIntegration:
    """Integration tests for service dependency tools."""

    def test_all_tools_return_valid_json(self):
        """Test that all tools return valid JSON."""
        tools_and_args = [
            (build_service_dependency_graph, {"dataset_id": "proj.ds"}),
            (analyze_upstream_downstream_impact, {
                "dataset_id": "proj.ds",
                "service_name": "svc",
            }),
            (detect_circular_dependencies, {"dataset_id": "proj.ds"}),
            (find_hidden_dependencies, {"dataset_id": "proj.ds"}),
        ]

        for tool, args in tools_and_args:
            result = tool(**args)
            parsed = json.loads(result)

            assert isinstance(parsed, dict)
            assert "sql_query" in parsed or "dependency_graph_sql" in parsed

    def test_all_tools_include_next_steps(self):
        """Test that all tools include next steps guidance."""
        tools_and_args = [
            (build_service_dependency_graph, {"dataset_id": "proj.ds"}),
            (analyze_upstream_downstream_impact, {
                "dataset_id": "proj.ds",
                "service_name": "svc",
            }),
            (detect_circular_dependencies, {"dataset_id": "proj.ds"}),
            (find_hidden_dependencies, {"dataset_id": "proj.ds"}),
        ]

        for tool, args in tools_and_args:
            result = tool(**args)
            parsed = json.loads(result)

            assert "next_steps" in parsed, f"{tool.__name__} missing next_steps"
            assert len(parsed["next_steps"]) > 0

    def test_sql_queries_have_basic_structure(self):
        """Test that SQL queries have basic SELECT/FROM structure."""
        tools_and_args = [
            (build_service_dependency_graph, {"dataset_id": "proj.ds"}),
            (analyze_upstream_downstream_impact, {
                "dataset_id": "proj.ds",
                "service_name": "svc",
            }),
            (detect_circular_dependencies, {"dataset_id": "proj.ds"}),
            (find_hidden_dependencies, {"dataset_id": "proj.ds"}),
        ]

        for tool, args in tools_and_args:
            result = tool(**args)
            parsed = json.loads(result)

            # Get the SQL query (different key names)
            sql = parsed.get("sql_query") or parsed.get("dependency_graph_sql")

            assert "SELECT" in sql, f"{tool.__name__} SQL missing SELECT"
            assert "FROM" in sql, f"{tool.__name__} SQL missing FROM"

    def test_dependency_graph_includes_both_sqls(self):
        """Test that dependency graph includes both main and topology SQL."""
        result = build_service_dependency_graph(dataset_id="proj.ds")
        parsed = json.loads(result)

        assert "dependency_graph_sql" in parsed
        assert "topology_sql" in parsed

        # Both should be valid SQL
        for sql_key in ["dependency_graph_sql", "topology_sql"]:
            sql = parsed[sql_key]
            assert "SELECT" in sql
            assert "FROM" in sql

    def test_impact_analysis_targets_specific_service(self):
        """Test that impact analysis correctly targets the specified service."""
        service_name = "unique-target-service-12345"
        result = analyze_upstream_downstream_impact(
            dataset_id="proj.ds",
            service_name=service_name,
        )

        parsed = json.loads(result)
        assert parsed["target_service"] == service_name
        assert service_name in parsed["sql_query"]
