
import pytest
from trace_analyzer.tools.trace_client import TraceFilterBuilder

def test_empty_builder():
    fb = TraceFilterBuilder()
    assert fb.build() == ""

def test_add_latency():
    fb = TraceFilterBuilder()
    fb.add_latency(1000)
    assert fb.build() == "latency:1000ms"

def test_add_root_span_name():
    fb = TraceFilterBuilder()
    fb.add_root_span_name("/api/v1/users")
    assert fb.build() == "root:/api/v1/users"

def test_add_root_span_name_exact():
    fb = TraceFilterBuilder()
    fb.add_root_span_name("/api/v1/users", exact=True)
    assert fb.build() == "+root:/api/v1/users"

def test_add_span_name():
    fb = TraceFilterBuilder()
    fb.add_span_name("db.query")
    assert fb.build() == "span:db.query"

def test_add_span_name_exact():
    fb = TraceFilterBuilder()
    fb.add_span_name("db.query", exact=True)
    assert fb.build() == "+span:db.query"

def test_add_span_name_root_only():
    fb = TraceFilterBuilder()
    fb.add_span_name("db.query", root_span=True)
    assert fb.build() == "^span:db.query"

def test_add_span_name_root_only_exact():
    fb = TraceFilterBuilder()
    fb.add_span_name("db.query", exact=True, root_span=True)
    assert fb.build() == "+^span:db.query"

def test_add_attribute_simple():
    fb = TraceFilterBuilder()
    fb.add_attribute("service.name", "frontend")
    assert fb.build() == "service.name:frontend"

def test_add_attribute_quoted():
    fb = TraceFilterBuilder()
    fb.add_attribute("error.message", "Something went wrong")
    # Should be quoted
    assert fb.build() == 'error.message:"Something went wrong"'

def test_add_attribute_quoted_escape():
    fb = TraceFilterBuilder()
    fb.add_attribute("msg", 'Hello "World"')
    # Should escape quotes
    assert fb.build() == 'msg:"Hello \\"World\\""'

def test_add_attribute_root_only():
    fb = TraceFilterBuilder()
    fb.add_attribute("http.status_code", 500, root_span=True)
    assert fb.build() == "^http.status_code:500"

def test_add_attribute_exact():
    fb = TraceFilterBuilder()
    fb.add_attribute("version", "v1.2.3", exact=True)
    assert fb.build() == "+version:v1.2.3"

def test_add_attribute_root_exact():
    fb = TraceFilterBuilder()
    fb.add_attribute("region", "us-east-1", exact=True, root_span=True)
    assert fb.build() == "+^region:us-east-1"

def test_chained_calls():
    fb = TraceFilterBuilder()
    filter_str = (
        fb.add_latency(500)
          .add_root_span_name("/checkout", exact=True)
          .add_attribute("error", "true")
          .build()
    )
    assert filter_str == "latency:500ms +root:/checkout error:true"

def test_complex_scenario():
    # User wants: Root span name starts with "/api", latency > 1s, service "payment", error true
    fb = TraceFilterBuilder()
    fb.add_root_span_name("/api")
    fb.add_latency(1000)
    fb.add_attribute("service", "payment")
    fb.add_attribute("error", "true", root_span=True) # Maybe user wants error on root span?

    expected = "root:/api latency:1000ms service:payment ^error:true"
    assert fb.build() == expected
