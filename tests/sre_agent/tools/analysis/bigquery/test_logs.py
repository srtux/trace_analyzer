import json

from sre_agent.tools.analysis.bigquery.logs import analyze_bigquery_log_patterns


def test_analyze_bigquery_log_patterns_generates_sql():
    """Test that the tool generates valid SQL with correct masking."""
    result_json = analyze_bigquery_log_patterns(
        dataset_id="my_dataset",
        table_name="_AllLogs",
        time_window_hours=48,
        service_name="frontend",
        severity="ERROR",
        limit=10,
    )

    result = json.loads(result_json)
    assert result["analysis_type"] == "bigquery_log_patterns"

    sql = result["sql_query"]
    assert "FROM `my_dataset._AllLogs`" in sql
    assert "timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 48 HOUR)" in sql
    assert (
        "JSON_EXTRACT_SCALAR(resource.attributes, '$.service.name') = 'frontend'" in sql
    )
    assert "severity_text = 'ERROR'" in sql
    assert "REGEXP_REPLACE(body.string_value" in sql
    assert "<UUID>" in sql
    assert "<IP>" in sql
    assert "LIMIT 10" in sql
