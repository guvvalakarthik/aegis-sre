"""Ground-truth labels and observed-run validation for remediation playbooks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Mapping, Sequence


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class TimelineEvent:
    name: str
    offset_seconds: float
    evidence_ids: tuple[str, ...]

    def validate(self) -> None:
        if not self.name or self.offset_seconds < 0 or not self.evidence_ids:
            raise ValueError("timeline events require name, non-negative offset, and evidence")


@dataclass(frozen=True)
class GroundTruth:
    scenario_id: str
    root_cause: str
    affected_services: tuple[str, ...]
    blast_radius: int
    severity: Severity
    expected_remediation: str
    recovery_signals: tuple[str, ...]
    symptoms: tuple[str, ...]
    cascading_effects: tuple[str, ...]
    timeline: tuple[TimelineEvent, ...]
    source_runs: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.scenario_id or not self.root_cause or not self.affected_services:
            raise ValueError("scenario identity, root cause, and affected services are required")
        if self.blast_radius < 1 or not self.expected_remediation or not self.recovery_signals:
            raise ValueError("blast radius, remediation, and recovery signals are required")
        if not self.symptoms or not self.timeline:
            raise ValueError("symptoms and timeline are required")
        for event in self.timeline:
            event.validate()

    def to_json(self) -> str:
        self.validate()
        return json.dumps(asdict(self), sort_keys=True, indent=2)


@dataclass(frozen=True)
class ObservedRun:
    run_id: str
    observed_root_cause: str
    affected_services: tuple[str, ...]
    observed_blast_radius: int
    recovery_signals: frozenset[str]
    timeline_offsets: Mapping[str, float]

    def validate(self) -> None:
        if not self.run_id or not self.observed_root_cause or self.observed_blast_radius < 1:
            raise ValueError("observed run is incomplete")
        if any(offset < 0 for offset in self.timeline_offsets.values()):
            raise ValueError("observed timeline offsets must be non-negative")


@dataclass(frozen=True)
class LabelAccuracy:
    run_id: str
    root_cause_match: bool
    affected_services_recall: float
    blast_radius_within_tolerance: bool
    recovery_signal_recall: float
    timeline_within_tolerance: bool

    @property
    def accurate(self) -> bool:
        return (
            self.root_cause_match
            and self.affected_services_recall == 1.0
            and self.blast_radius_within_tolerance
            and self.recovery_signal_recall == 1.0
            and self.timeline_within_tolerance
        )


def compare_ground_truth(
    truth: GroundTruth,
    run: ObservedRun,
    *,
    blast_radius_tolerance: int = 0,
    timeline_tolerance_seconds: float = 5.0,
) -> LabelAccuracy:
    truth.validate()
    run.validate()
    if blast_radius_tolerance < 0 or timeline_tolerance_seconds < 0:
        raise ValueError("tolerances must be non-negative")
    expected_services = set(truth.affected_services)
    observed_services = set(run.affected_services)
    service_recall = len(expected_services & observed_services) / len(expected_services)
    expected_signals = set(truth.recovery_signals)
    signal_recall = len(expected_signals & set(run.recovery_signals)) / len(expected_signals)
    expected_times = {event.name: event.offset_seconds for event in truth.timeline}
    timeline_ok = all(
        name in run.timeline_offsets
        and abs(run.timeline_offsets[name] - offset) <= timeline_tolerance_seconds
        for name, offset in expected_times.items()
    )
    return LabelAccuracy(
        run.run_id,
        truth.root_cause == run.observed_root_cause,
        service_recall,
        abs(truth.blast_radius - run.observed_blast_radius) <= blast_radius_tolerance,
        signal_recall,
        timeline_ok,
    )


@dataclass(frozen=True)
class RemediationPlaybook:
    playbook_id: str
    scenario_id: str
    cause: str
    actions: tuple[str, ...]
    preconditions: tuple[str, ...]
    rollback_steps: tuple[str, ...]
    validation_signals: tuple[str, ...]
    tested_run_ids: tuple[str, ...] = ()

    def validate(self) -> None:
        if not all((
            self.playbook_id, self.scenario_id, self.cause, self.actions,
            self.preconditions, self.rollback_steps, self.validation_signals,
        )):
            raise ValueError("playbook requires actions, preconditions, rollback, and validation")

    def verify_against(self, truth: GroundTruth, runs: Sequence[ObservedRun]) -> None:
        self.validate()
        truth.validate()
        if self.scenario_id != truth.scenario_id or self.cause != truth.root_cause:
            raise ValueError("playbook is not linked to the ground-truth cause")
        if not runs or any(run.run_id not in self.tested_run_ids for run in runs):
            raise ValueError("playbook must identify every validation run")
        if set(self.validation_signals) - set(truth.recovery_signals):
            raise ValueError("playbook validation uses undeclared recovery signals")
