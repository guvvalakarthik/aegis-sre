"""Canonical, provenance-preserving telemetry records."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress

SchemaVersion = Literal["telemetry.v1"]
SignalKind = Literal["log", "metric", "trace", "deployment", "kubernetes_event"]
Severity = Literal["debug", "info", "warn", "error", "fatal"]
Environment = Annotated[str, Field(min_length=1, max_length=64)]
ServiceName = Annotated[str, Field(min_length=1, max_length=128)]


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = Field(min_length=1, max_length=256)
    source_id: str = Field(min_length=1, max_length=256)
    collected_at: datetime
    schema_version: SchemaVersion = "telemetry.v1"
    redacted: bool = False


class ResourceIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    service_name: ServiceName
    service_namespace: str | None = Field(default=None, max_length=128)
    service_version: str | None = Field(default=None, max_length=128)
    environment: Environment
    host_name: str | None = Field(default=None, max_length=256)
    pod_name: str | None = Field(default=None, max_length=256)
    container_name: str | None = Field(default=None, max_length=256)
    node_name: str | None = Field(default=None, max_length=256)


class TelemetryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str = Field(min_length=1, max_length=256)
    kind: SignalKind
    observed_at: datetime
    received_at: datetime
    resource: ResourceIdentity
    provenance: Provenance
    trace_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    span_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)


class LogRecord(TelemetryRecord):
    kind: Literal["log"] = "log"
    severity: Severity = "info"
    body: str = Field(max_length=32_768)


class MetricRecord(TelemetryRecord):
    kind: Literal["metric"] = "metric"
    metric_name: str = Field(min_length=1, max_length=256)
    value: float
    unit: str | None = Field(default=None, max_length=64)
    labels: dict[str, str] = Field(default_factory=dict)


class TraceRecord(TelemetryRecord):
    kind: Literal["trace"] = "trace"
    operation_name: str = Field(min_length=1, max_length=256)
    duration_ms: float = Field(ge=0)
    status: Literal["unset", "ok", "error"] = "unset"
    parent_span_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")


class DeploymentChange(TelemetryRecord):
    kind: Literal["deployment"] = "deployment"
    change_type: Literal["deploy", "rollback", "config", "scale"]
    revision: str = Field(min_length=1, max_length=256)
    actor: str | None = Field(default=None, max_length=256)


class KubernetesEvent(TelemetryRecord):
    kind: Literal["kubernetes_event"] = "kubernetes_event"
    namespace: str = Field(min_length=1, max_length=128)
    object_kind: str = Field(min_length=1, max_length=128)
    object_name: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=1, max_length=256)
    event_type: Literal["Normal", "Warning"]
    message: str = Field(max_length=8_192)
    count: int = Field(default=1, ge=1)
    source_ip: IPvAnyAddress | None = None
