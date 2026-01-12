"""Pydantic schemas for BigQuery OTel and LogEntry data."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BigQuerySpan(BaseModel):
    """Represents a Trace Span in BigQuery OTel schema."""

    model_config = ConfigDict(populate_by_name=True)

    trace_id: str = Field(..., alias="trace_id")
    span_id: str = Field(..., alias="span_id")
    parent_span_id: str | None = Field(None, alias="parent_span_id")
    name: str | None = None
    kind: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    status: dict[str, Any] | None = None  # e.g. {"code": 1, "message": "error"}
    attributes: dict[str, Any] | None = None
    resource: dict[str, Any] | None = None  # Resource attributes (service.name, etc.)
    links: list[dict[str, Any]] | None = None
    events: list[dict[str, Any]] | None = None

    # Custom/Flexible fields can be caught by extra="ignore" in default pydantic
    # or explicitly mapped if needed. For now we stick to core strictness but allow flexibility via dicts.


class BigQueryLogEntry(BaseModel):
    """Represents a Log Entry in BigQuery."""

    model_config = ConfigDict(populate_by_name=True)

    log_name: str | None = None
    resource: dict[str, Any] | None = None
    text_payload: str | None = None
    json_payload: dict[str, Any] | None = None
    timestamp: datetime | None = None
    severity: str | None = None
    insert_id: str | None = None
    labels: dict[str, Any] | None = None
    trace: str | None = None
    span_id: str | None = None
    trace_sampled: bool | None = None
