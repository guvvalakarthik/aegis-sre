"""Incident-lab and data-quality integration gate contracts."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Sequence


class ReproductionStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class LabManifest:
    lab_version: str
    scenario_catalog_version: str
    ground_truth_version: str
    feature_schema_version: str
    dataset_hash: str
    quality_report_hash: str
    environment_version: str

    def digest(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class ScenarioEvidence:
    scenario_id: str
    run_id: str
    reproduction_hash: str
    status: ReproductionStatus
    ground_truth_match: bool
    quality_passed: bool
    clean_environment: bool
    metrics: dict[str, float]
    limitations: tuple[str, ...] = ()

    def validate(self) -> None:
        if not all((self.scenario_id, self.run_id, self.reproduction_hash)):
            raise ValueError("scenario evidence identity is required")
        if not self.clean_environment:
            raise ValueError("scenario evidence must come from a clean environment")
        if any(not math.isfinite(value) or value < 0 for value in self.metrics.values()):
            raise ValueError("scenario metrics must be finite and non-negative")
        if self.status == ReproductionStatus.PASSED and not self.ground_truth_match:
            raise ValueError("passed reproduction must match ground truth")
        if not self.quality_passed and not self.limitations:
            raise ValueError("quality exceptions require documented limitations")


@dataclass(frozen=True)
class Approval:
    contributor: str
    manifest_digest: str
    rationale_hash: str


@dataclass(frozen=True)
class LabReport:
    manifest: LabManifest
    scenarios: tuple[ScenarioEvidence, ...]
    known_gaps: tuple[str, ...]
    ood_scenarios: tuple[str, ...]
    approvals: tuple[Approval, ...] = ()

    def validate(self) -> None:
        if not self.scenarios:
            raise ValueError("incident lab report cannot be empty")
        if not self.known_gaps or not self.ood_scenarios:
            raise ValueError("known gaps and OOD scenarios must be documented")
        if len({scenario.scenario_id for scenario in self.scenarios}) != len(self.scenarios):
            raise ValueError("duplicate scenario evidence")
        for scenario in self.scenarios:
            scenario.validate()
        if any(approval.manifest_digest != self.manifest.digest() for approval in self.approvals):
            raise ValueError("approval does not match lab manifest")

    def approve(self, contributor: str, rationale: str) -> "LabReport":
        self.validate()
        if not contributor or not rationale:
            raise ValueError("approval identity and rationale are required")
        approval = Approval(
            contributor,
            self.manifest.digest(),
            hashlib.sha256(rationale.encode()).hexdigest(),
        )
        prior = tuple(item for item in self.approvals if item.contributor != contributor)
        return LabReport(self.manifest, self.scenarios, self.known_gaps, self.ood_scenarios, prior + (approval,))

    def independently_approved(self, contributors: Sequence[str]) -> bool:
        self.validate()
        return set(contributors).issubset({item.contributor for item in self.approvals})

    def ready_for_modeling(self, contributors: Sequence[str]) -> bool:
        self.validate()
        return (
            self.independently_approved(contributors)
            and all(item.status == ReproductionStatus.PASSED for item in self.scenarios)
            and all(item.ground_truth_match for item in self.scenarios)
        )
