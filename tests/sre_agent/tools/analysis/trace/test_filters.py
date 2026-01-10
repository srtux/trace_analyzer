from sre_agent.tools.analysis.trace.filters import TraceQueryBuilder


def test_builder_init():
    builder = TraceQueryBuilder()
    assert builder.build() == ""


def test_span_name():
    builder = TraceQueryBuilder()
    builder.span_name("my-span")
    assert builder.build() == "span:my-span"

    builder.clear()
    builder.span_name("my-span", match_exact=True)
    assert builder.build() == "+span:my-span"

    builder.clear()
    builder.span_name("my-span", root_only=True)
    assert builder.build() == "root:my-span"


def test_latency():
    builder = TraceQueryBuilder()
    builder.latency(min_latency_ms=500)
    assert builder.build() == "latency:500ms"


def test_attribute():
    builder = TraceQueryBuilder()
    builder.attribute("key", "value")
    assert builder.build() == "key:value"

    builder.clear()
    builder.attribute("key", "value", match_exact=True)
    assert builder.build() == "+key:value"

    builder.clear()
    builder.attribute("key", "value", root_only=True)
    assert builder.build() == "^key:value"

    builder.clear()
    builder.attribute("key", "value", match_exact=True, root_only=True)
    # The implementation produces "+^key:value" because match_exact adds "+" and root_only adds "^".
    # Docs example shows "+^url:[VALUE]", so this is correct.
    assert builder.build() == "+^key:value"


def test_complex_query():
    builder = TraceQueryBuilder()
    (
        builder.span_name("root_op", root_only=True)
        .latency(min_latency_ms=100)
        .status(500)
        .method("GET")
    )

    assert (
        builder.build() == "root:root_op latency:100ms /http/status_code:500 method:GET"
    )


def test_mix_root_and_normal():
    builder = TraceQueryBuilder()
    builder.span_name("main", root_only=True).span_name("db_query")
    assert builder.build() == "root:main span:db_query"


def test_url_method():
    builder = TraceQueryBuilder()
    builder.url("/api/v1").method("POST", root_only=True)
    assert builder.build() == "url:/api/v1 ^method:POST"
