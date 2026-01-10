"""Decorators for SRE Agent tools with OpenTelemetry instrumentation."""

import functools
import inspect
import logging
import time
from collections.abc import Callable
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)

# Initialize OTel instruments
tracer = trace.get_tracer("sre_agent.tools")
meter = metrics.get_meter("sre_agent.tools")

tool_execution_duration = meter.create_histogram(
    name="sre_agent.tool.execution_duration",
    description="Duration of tool executions",
    unit="ms",
)
tool_execution_count = meter.create_counter(
    name="sre_agent.tool.execution_count",
    description="Total number of tool calls",
    unit="1",
)


def adk_tool(func: Callable[..., Any]) -> Callable[..., Any]:  # noqa: C901
    """
    Decorator to mark a function as an ADK tool and provide automatic
    logging and instrumentation.

    This decorator provides:
    - OTel Spans for every execution
    - OTel Metrics (count and duration)
    - Standardized Logging of args and results/errors
    - Error handling (ensures errors are logged before raising/returning)

    Example:
        @adk_tool
        async def fetch_trace(trace_id: str) -> dict:
            ...
    """

    def _record_attributes(span, bound_args):
        for k, v in bound_args.arguments.items():
            # Truncate long strings to avoid span attribute limits
            val_str = str(v)
            if len(val_str) > 1000:
                val_str = val_str[:1000] + "...(truncated)"
            span.set_attribute(f"arg.{k}", val_str)

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        tool_name = func.__name__
        start_time = time.time()
        success = True

        with tracer.start_as_current_span(tool_name) as span:
            span.set_attribute("tool.name", tool_name)
            span.set_attribute("code.function", tool_name)

            # Log calling
            try:
                sig = inspect.signature(func)
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                arg_str = ", ".join(
                    f"{k}={repr(v)[:200]}" for k, v in bound.arguments.items()
                )
                _record_attributes(span, bound)
            except Exception:
                arg_str = f"args={args}, kwargs={kwargs}"

            logger.info(f"Tool '{tool_name}' called with: {arg_str}")

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                logger.info(f"Tool '{tool_name}' completed in {duration_ms:.2f}ms")
                return result
            except Exception as e:
                success = False
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"Tool '{tool_name}' failed after {duration_ms:.2f}ms: {e}",
                    exc_info=True,
                )
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise e
            finally:
                duration_ms = (time.time() - start_time) * 1000
                tool_execution_duration.record(
                    duration_ms, {"tool.name": tool_name, "success": str(success)}
                )
                tool_execution_count.add(
                    1, {"tool.name": tool_name, "success": str(success)}
                )

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        tool_name = func.__name__
        start_time = time.time()
        success = True

        with tracer.start_as_current_span(tool_name) as span:
            span.set_attribute("tool.name", tool_name)
            span.set_attribute("code.function", tool_name)

            # Log calling
            try:
                sig = inspect.signature(func)
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                arg_str = ", ".join(
                    f"{k}={repr(v)[:200]}" for k, v in bound.arguments.items()
                )
                _record_attributes(span, bound)
            except Exception:
                arg_str = f"args={args}, kwargs={kwargs}"

            logger.info(f"Tool '{tool_name}' called with: {arg_str}")

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                logger.info(f"Tool '{tool_name}' completed in {duration_ms:.2f}ms")
                return result
            except Exception as e:
                success = False
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"Tool '{tool_name}' failed after {duration_ms:.2f}ms: {e}",
                    exc_info=True,
                )
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise e
            finally:
                duration_ms = (time.time() - start_time) * 1000
                tool_execution_duration.record(
                    duration_ms, {"tool.name": tool_name, "success": str(success)}
                )
                tool_execution_count.add(
                    1, {"tool.name": tool_name, "success": str(success)}
                )

    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper
