"""Replayable, provenance-preserving evidence-package contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Sequence


class EvidenceKind(StrEnum):
    MODEL_SIGNAL = "model_signal"
    GRAPH = "graph"
    RETRIEVAL = "retrieval"
    CITATION = "citation"
    GROUND_TRUTH = "ground_truth"


class PackageStatus(StrEnum):
    GROUNDED = "grounded"
    CONTRADICTORY = "contradictory"
    INSUFFICIENT = "insufficient"
    ABSTAINED = "abstained"


@dataclass(frozen=True)
class Provenance:
    source_id: str
    source_version: str
    captured_at: str
    source_hash: str


@dataclass(frozen=True)
class EvidenceItem:
    item_id: str
    kind: EvidenceKind
    value: Any
    provenance: Provenance
    confidence: float | None
    environment: str
    authorized_roles: frozenset[str]

    def validate(self) -> None:
        if not self.item_id or not self.environment or not self.authorized_roles:
            raise ValueError("evidence identity, environment, and authorization are required")
        if not self.provenance.source_id or not self.provenance.source_version:
            raise ValueError("source provenance is required")
        if not self.provenance.captured_at or not self.provenance.source_hash:
            raise ValueError("capture timestamp and source hash are required")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")


@dataclass(frozen=True)
class Approval:
    contributor: str
    approval_hash: str


@dataclass(frozen=True)
class EvidencePackage:
    package_id: str
    incident_id: str
    incident_time: str
    environment: str
    package_version: str
    items: tuple[EvidenceItem, ...]
    status: PackageStatus
    missing_evidence: tuple[str, ...]
    contradictions: tuple[tuple[str, str], ...]
    abstained: bool
    approvals: tuple[Approval, ...] = ()

    def validate(self) -> None:
        if not self.package_id or not self.incident_id or not self.incident_time:
            raise ValueError("package identity and incident time are required")
        if not self.items and not self.missing_evidence and not self.abstained:
            raise ValueError("empty package must explicitly record missing evidence or abstention")
        for item in self.items:
            item.validate()
            if item.environment != self.environment:
                raise ValueError("cross-environment evidence is forbidden")
        if self.status == PackageStatus.CONTRADICTORY and not self.contradictions:
            raise ValueError("contradictory package must preserve contradiction pairs")
        if self.status == PackageStatus.ABSTAINED and not self.abstained:
            raise ValueError("abstained status requires abstained=true")

    def approve(self, contributor: str, rationale: str) -> "EvidencePackage":
        self.validate()
        if not contributor or not rationale:
            raise ValueError("approval identity and rationale are required")
        approval = Approval(contributor, hashlib.sha256(rationale.encode()).hexdigest())
        prior = tuple(item for item in self.approvals if item.contributor != contributor)
        return EvidencePackage(
            **{**asdict(self), "approvals": prior + (approval,)}
        )

    def approved_by(self, contributors: Sequence[str]) -> bool:
        return set(contributors).issubset({item.contributor for item in self.approvals})

    def authorized_items(self, roles: Sequence[str]) -> tuple[EvidenceItem, ...]:
        role_set = frozenset(roles)
        if not role_set:
            raise PermissionError("caller roles are required")
        return tuple(item for item in self.items if item.authorized_roles.intersection(role_set))

    def to_json(self) -> str:
        self.validate()
        return json.dumps(asdict(self), sort_keys=True, indent=2)


def make_package_id(incident_id: str, incident_time: str, environment: str) -> str:
    if not incident_id or not incident_time or not environment:
        raise ValueError("incident identity is required")
    return hashlib.sha256(f"{incident_id}\0{incident_time}\0{environment}".encode()).hexdigest()


def detect_contradictions(items: Sequence[EvidenceItem], *, field: str) -> tuple[tuple[str, str], ...]:
    """Return conflicting values without choosing a winner or hiding either item."""
    grouped: dict[str, list[EvidenceItem]] = {}
    for item in items:
        value = item.value.get(field) if isinstance(item.value, dict) else None
        if value is not None:
            grouped.setdefault(field, []).append(item)
    values = {str(item.value[field]) for item in grouped.get(field, [])}
    if len(values) <= 1:
        return ()
    ids = tuple(item.item_id for item in grouped[field])
    return tuple((ids[index], ids[index + 1]) for index in range(len(ids) - 1))


def replay_package(serialized: str) -> EvidencePackage:
    raw = json.loads(serialized)
    items = tuple(
        EvidenceItem(
            item_id=item["item_id"],
            kind=EvidenceKind(item["kind"]),
            value=item["value"],
            provenance=Provenance(**item["provenance"]),
            confidence=item["confidence"],
            environment=item["environment"],
            authorized_roles=frozenset(item["authorized_roles"]),
        )
        for item in raw["items"]
    )
    approvals = tuple(Approval(**approval) for approval in raw.get("approvals", []))
    package = EvidencePackage(
        package_id=raw["package_id"],
        incident_id=raw["incident_id"],
        incident_time=raw["incident_time"],
        environment=raw["environment"],
        package_version=raw["package_version"],
        items=items,
        status=PackageStatus(raw["status"]),
        missing_evidence=tuple(raw["missing_evidence"]),
        contradictions=tuple(tuple(pair) for pair in raw["contradictions"]),
        abstained=raw["abstained"],
        approvals=approvals,
    )
    package.validate()
    return package
