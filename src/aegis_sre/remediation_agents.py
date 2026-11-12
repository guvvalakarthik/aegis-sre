"""Allowlisted remediation planning, verification, rollback, and postmortem contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Mapping, Sequence


class RemediationStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    EXECUTED = "executed"
    VERIFIED = "verified"
    ROLLED_BACK = "rolled_back"
    ESCALATED = "escalated"


class PostmortemKind(StrEnum):
    FACT = "fact"
    INFERENCE = "inference"
    RECOMMENDATION = "recommendation"


@dataclass(frozen=True)
class RemediationOperation:
    name: str
    allowed_causes: frozenset[str]
    execute: Callable[[Mapping[str, str]], str]
    rollback: Callable[[Mapping[str, str]], str]


@dataclass(frozen=True)
class RemediationPlan:
    plan_id: str
    diagnosed_cause: str
    operation: str
    preconditions: tuple[str, ...]
    expected_effect: str
    risk: str
    canary: str
    validation: tuple[str, ...]
    rollback: str
    parameters: Mapping[str, str]
    status: RemediationStatus = RemediationStatus.PROPOSED

    def validate(self, operations: Mapping[str, RemediationOperation]) -> None:
        if self.operation not in operations:
            raise ValueError("operation is not allowlisted")
        if self.diagnosed_cause not in operations[self.operation].allowed_causes:
            raise ValueError("operation is not approved for diagnosed cause")
        if not all((
            self.plan_id, self.diagnosed_cause, self.preconditions, self.expected_effect,
            self.risk, self.canary, self.validation, self.rollback,
        )):
            raise ValueError("plan requires preconditions, effect, risk, canary, validation, and rollback")


@dataclass(frozen=True)
class VerificationEvidence:
    health_ok: bool
    slo_ok: bool
    telemetry_ok: bool
    recurrence_free: bool
    observed_at: str
    evidence_ids: tuple[str, ...]

    @property
    def recovered(self) -> bool:
        return all((self.health_ok, self.slo_ok, self.telemetry_ok, self.recurrence_free)) and bool(self.evidence_ids)


@dataclass(frozen=True)
class PostmortemEntry:
    kind: PostmortemKind
    statement: str
    evidence_ids: tuple[str, ...]
    owner: str | None = None

    def validate(self) -> None:
        if not self.statement or (self.kind != PostmortemKind.RECOMMENDATION and not self.evidence_ids):
            raise ValueError("facts and inferences require evidence; statements are required")


@dataclass(frozen=True)
class Postmortem:
    incident_id: str
    timeline: tuple[str, ...]
    impact: str
    cause: str
    actions: tuple[str, ...]
    entries: tuple[PostmortemEntry, ...]
    prevention_work: tuple[str, ...]

    def validate(self) -> None:
        if not self.incident_id or not self.timeline or not self.impact or not self.cause:
            raise ValueError("postmortem identity, timeline, impact, and cause are required")
        for entry in self.entries:
            entry.validate()


class RemediationController:
    def __init__(self, operations: Sequence[RemediationOperation]) -> None:
        self.operations = {operation.name: operation for operation in operations}
        if not self.operations:
            raise ValueError("at least one allowlisted operation is required")

    def approve(self, plan: RemediationPlan) -> RemediationPlan:
        plan.validate(self.operations)
        return RemediationPlan(**{**plan.__dict__, "status": RemediationStatus.APPROVED})

    def execute(self, plan: RemediationPlan) -> tuple[RemediationPlan, str]:
        plan.validate(self.operations)
        if plan.status != RemediationStatus.APPROVED:
            raise ValueError("only approved plans may execute")
        result = self.operations[plan.operation].execute(plan.parameters)
        return RemediationPlan(**{**plan.__dict__, "status": RemediationStatus.EXECUTED}), result

    def verify_or_recover(
        self,
        plan: RemediationPlan,
        evidence: VerificationEvidence,
    ) -> tuple[RemediationPlan, str]:
        if plan.status != RemediationStatus.EXECUTED:
            raise ValueError("only executed plans may be verified")
        if evidence.recovered:
            return RemediationPlan(**{**plan.__dict__, "status": RemediationStatus.VERIFIED}), "recovered"
        try:
            result = self.operations[plan.operation].rollback(plan.parameters)
            return RemediationPlan(**{**plan.__dict__, "status": RemediationStatus.ROLLED_BACK}), result
        except Exception as exc:
            return RemediationPlan(**{**plan.__dict__, "status": RemediationStatus.ESCALATED}), f"rollback failed: {exc}"
