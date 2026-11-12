"""Replayable incident bundles with lifecycle and contamination controls."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CapturePhase(StrEnum):
    BASELINE = "baseline"
    INJECTION = "injection"
    PROPAGATION = "propagation"
    MITIGATION = "mitigation"
    RECOVERY = "recovery"


class BundleStatus(StrEnum):
    CAPTURING = "capturing"
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    CONTAMINATED = "contaminated"


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str = Field(min_length=1, max_length=256)
    phase: CapturePhase
    observed_at: datetime
    source: str = Field(min_length=1, max_length=256)
    payload: dict[str, Any]
    normalized: dict[str, Any]
    clock_offset_ms: int = 0
    provenance: str = Field(min_length=1, max_length=512)


class GroundTruth(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    root_cause: str = Field(min_length=1, max_length=256)
    causal_resource: str = Field(min_length=1, max_length=256)
    affected_services: tuple[str, ...] = Field(min_length=1)
    severity: str = Field(min_length=1, max_length=32)
    valid_remediation: str = Field(min_length=1, max_length=256)
    recovery_slo_met: bool


class CleanupResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    attempted_at: datetime
    restored_health: bool
    restored_slo: bool
    details: str = Field(min_length=1, max_length=2_048)


class IncidentBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_id: str = Field(min_length=1, max_length=256)
    scenario_id: str = Field(min_length=1, max_length=128)
    schema_version: str = "incident-bundle.v1"
    status: BundleStatus = BundleStatus.CAPTURING
    started_at: datetime
    completed_at: datetime | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    ground_truth: GroundTruth
    cleanup: CleanupResult | None = None
    contaminated_reason: str | None = None

    def append(self, evidence: Evidence) -> None:
        if self.status not in {BundleStatus.CAPTURING, BundleStatus.INCOMPLETE}:
            raise ValueError("only active or resumable bundles accept evidence")
        self.evidence.append(evidence)

    def mark_interrupted(self, reason: str) -> None:
        if not reason:
            raise ValueError("interruption reason is required")
        self.status = BundleStatus.INCOMPLETE
        self.contaminated_reason = reason

    def complete(self, completed_at: datetime, cleanup: CleanupResult) -> None:
        if not cleanup.restored_health or not cleanup.restored_slo:
            self.status = BundleStatus.CONTAMINATED
            self.contaminated_reason = "cleanup did not restore preflight health and SLO"
            return
        phases = {item.phase for item in self.evidence}
        required = set(CapturePhase)
        if phases != required:
            self.status = BundleStatus.INCOMPLETE
            self.contaminated_reason = "required capture phases are missing"
            return
        self.completed_at = completed_at
        self.cleanup = cleanup
        self.status = BundleStatus.COMPLETE

    def training_eligible(self) -> bool:
        return self.status == BundleStatus.COMPLETE and self.cleanup is not None


def bundle_fingerprint(bundle: IncidentBundle) -> str:
    canonical = json.dumps(bundle.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def replay(bundle: IncidentBundle) -> list[dict[str, Any]]:
    """Replay normalized evidence offline; incomplete/contaminated bundles are rejected."""
    if not bundle.training_eligible():
        raise ValueError("only complete, clean bundles can be replayed")
    return [
        {
            "phase": evidence.phase,
            "observed_at": evidence.observed_at.isoformat(),
            "source": evidence.source,
            "normalized": evidence.normalized,
        }
        for evidence in sorted(bundle.evidence, key=lambda item: (item.observed_at, item.evidence_id))
    ]
