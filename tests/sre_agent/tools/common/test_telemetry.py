from unittest import mock

from sre_agent.tools.common.telemetry import get_meter, get_tracer


def test_get_tracer():
    with mock.patch(
        "sre_agent.tools.common.telemetry.trace.get_tracer_provider"
    ) as mock_get_provider:
        mock_tracer = mock.Mock()
        mock_get_provider.return_value = mock_tracer

        tracer = get_tracer("test_module")

        mock_get_provider.assert_called_once()
        assert tracer == mock_tracer.get_tracer.return_value


def test_get_meter():
    with mock.patch(
        "sre_agent.tools.common.telemetry.metrics.get_meter"
    ) as mock_get_meter:
        mock_meter = mock.Mock()
        mock_get_meter.return_value = mock_meter

        meter = get_meter("test_module")

        mock_get_meter.assert_called_with("test_module")
        assert meter == mock_meter


def test_logging_filter():
    import logging

    from sre_agent.tools.common.telemetry import _FunctionCallWarningFilter

    log_filter = _FunctionCallWarningFilter()

    # Record that should be filtered out
    record_filtered = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="path",
        lineno=1,
        msg="Warning: there are non-text parts in the response",
        args=(),
        exc_info=None,
    )
    assert not log_filter.filter(record_filtered)

    # Record that should NOT be filtered out
    record_allowed = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="path",
        lineno=1,
        msg="Some other warning",
        args=(),
        exc_info=None,
    )
    assert log_filter.filter(record_allowed)
