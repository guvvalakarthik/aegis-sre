"""Validation, redaction, quarantine, and deterministic deduplication."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from aegis_sre.telemetry.contracts import (
    DeploymentChange,
    KubernetesEvent,
    LogRecord,
    MetricRecord,
    TelemetryRecord,
    TraceRecord,
)

_RECORD_TYPES = (LogRecord, MetricRecord, TraceRecord, DeploymentChange, KubernetesEvent)
_SENSITIVE_KEY = re.compile(r"(password|passwd|secret|token|api[_-]?key|authorization|cookie)", re.I)
_SENSITIVE_VALUE = re.compile(r"(?i)(bearer\s+|gh[pousr]_)[A-Za-z0-9._-]+")


class QuarantineRecord:
    """An invalid input retained for diagnosis without entering the evidence store."""

    def __init__(self, payload: Mapping[str, Any], reason: str, quarantined_at: datetime) -> None:
        self.payload = dict(payload)
        self.reason = reason
        self.quarantined_at = quarantined_at


def redact(value: Any) -> tuple[Any, bool]:
    """Recursively redact secret-like keys and credential-shaped strings."""
    changed = False
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in value.items():
            if _SENSITIVE_KEY.search(str(key)):
                output[str(key)] = "[REDACTED]"
                changed = True
            else:
                output[str(key)], item_changed = redact(item)
                changed |= item_changed
        return output, changed
    if isinstance(value, list):
        output_list = []
        for item in value:
            redacted, item_changed = redact(item)
            output_list.append(redacted)
            changed |= item_changed
        return output_list, changed
    if isinstance(value, str) and _SENSITIVE_VALUE.search(value):
        return "[REDACTED]", True
    return value, False


def record_type(payload: Mapping[str, Any]) -> type[TelemetryRecord]:
    kind = payload.get("kind")
    for model in _RECORD_TYPES:
        if model.model_fields["kind"].default == kind:
            return model
    raise ValueError(f"unsupported telemetry kind: {kind!r}")


class InMemoryIngestStore:
    """Deterministic reference store; production adapters can implement the same contract."""

    def __init__(self) -> None:
        self.records: dict[str, TelemetryRecord] = {}
        self.quarantine: list[QuarantineRecord] = []

    def ingest(self, payload: Mapping[str, Any]) -> TelemetryRecord | None:
        cleaned, was_redacted = redact(payload)
        try:
            model = record_type(cleaned).model_validate(cleaned)
        except (ValidationError, ValueError) as exc:
            self.quarantine.append(
                QuarantineRecord(
                    payload=cleaned,
                    reason=str(exc),
                    quarantined_at=datetime.now(timezone.utc),
                )
            )
            return None

        if was_redacted:
            provenance = model.provenance.model_copy(update={"redacted": True})
            model = model.model_copy(update={"provenance": provenance})

        existing = self.records.get(model.record_id)
        if existing is None or model.received_at >= existing.received_at:
            self.records[model.record_id] = model
            return model
        return existing

    def fingerprint(self, record: TelemetryRecord) -> str:
        canonical = json.dumps(record.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
