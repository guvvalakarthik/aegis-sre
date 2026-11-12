"""Staged, citation-required diagnostic workflow contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Iterable


class DiagnosticStage(StrEnum):
    CREATED = "created"
    TRIAGED = "triaged"
    EVIDENCE_COLLECTION = "evidence_collection"
    HYPOTHESIS_TESTING = "hypothesis_testing"
    CRITIC_REVIEW = "critic_review"
    COMPLETE = "complete"
    ABSTAINED = "abstained"


@dataclass(frozen=True)
class DiagnosticBudget:
    max_tool_calls: int = 20
    max_hypotheses: int = 10
    max_root_causes: int = 3

    def validate(self) -> None:
        if min(self.max_tool_calls, self.max_hypotheses, self.max_root_causes) < 1:
            raise ValueError("diagnostic budgets must be positive")


@dataclass(frozen=True)
class EvidencePlan:
    queries: tuple[str, ...]
    required_sources: tuple[str, ...]

    def validate(self) -> None:
        if not self.queries or not all(query.strip() for query in self.queries):
            raise ValueError("evidence plan requires non-empty queries")
        if not self.required_sources:
            raise ValueError("evidence plan requires source types")


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    source: str
    citation: str
    content: str
    timestamp: str

    def validate(self) -> None:
        if not all((self.evidence_id, self.source, self.citation, self.content, self.timestamp)):
            raise ValueError("evidence references require identity, source, citation, content, and time")


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    statement: str
    affected_services: tuple[str, ...]
    supporting: tuple[str, ...] = ()
    refuting: tuple[str, ...] = ()

    def score(self) -> float:
        return len(self.supporting) / max(1, len(self.supporting) + len(self.refuting))


@dataclass(frozen=True)
class RootCause:
    hypothesis_id: str
    statement: str
    score: float
    uncertainty: float
    affected_services: tuple[str, ...]
    citations: tuple[str, ...]


@dataclass(frozen=True)
class CriticReview:
    accepted_hypotheses: tuple[str, ...]
    rejected_hypotheses: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class DiagnosisReport:
    stage: DiagnosticStage
    root_causes: tuple[RootCause, ...]
    abstained: bool
    missing_evidence: tuple[str, ...]
    tool_calls: int
    cited_evidence: tuple[str, ...]


@dataclass(frozen=True)
class ReadOnlyTool:
    name: str
    source: str
    invoke: Callable[[str], EvidenceRef]
    read_only: bool = True


class DiagnosticWorkflow:
    def __init__(self, incident_id: str, budget: DiagnosticBudget | None = None) -> None:
        if not incident_id:
            raise ValueError("incident_id is required")
        self.incident_id = incident_id
        self.budget = budget or DiagnosticBudget()
        self.budget.validate()
        self.stage = DiagnosticStage.CREATED
        self.plan: EvidencePlan | None = None
        self.evidence: dict[str, EvidenceRef] = {}
        self.hypotheses: dict[str, Hypothesis] = {}
        self.tool_calls = 0
        self._idempotent: dict[str, EvidenceRef] = {}
        self._critic: CriticReview | None = None

    def triage(self, plan: EvidencePlan) -> None:
        if self.stage != DiagnosticStage.CREATED:
            raise ValueError("triage can only run once")
        plan.validate()
        self.plan = plan
        self.stage = DiagnosticStage.TRIAGED

    def collect(self, tool: ReadOnlyTool, query: str, *, idempotency_key: str) -> EvidenceRef:
        if self.stage not in {DiagnosticStage.TRIAGED, DiagnosticStage.EVIDENCE_COLLECTION}:
            raise ValueError("evidence collection is not allowed at this stage")
        if self.plan is None or query not in self.plan.queries:
            raise ValueError("query was not approved by the evidence plan")
        if not tool.read_only or not tool.name or tool.source not in self.plan.required_sources:
            raise PermissionError("only approved read-only tools may collect evidence")
        if not idempotency_key:
            raise ValueError("idempotency key is required")
        if idempotency_key in self._idempotent:
            return self._idempotent[idempotency_key]
        if self.tool_calls >= self.budget.max_tool_calls:
            raise RuntimeError("diagnostic tool budget exhausted")
        result = tool.invoke(query)
        result.validate()
        if result.source != tool.source:
            raise ValueError("tool returned evidence from an unexpected source")
        self.tool_calls += 1
        self.evidence[result.evidence_id] = result
        self._idempotent[idempotency_key] = result
        self.stage = DiagnosticStage.EVIDENCE_COLLECTION
        return result

    def add_hypothesis(self, hypothesis: Hypothesis) -> None:
        if self.stage not in {DiagnosticStage.EVIDENCE_COLLECTION, DiagnosticStage.HYPOTHESIS_TESTING}:
            raise ValueError("hypotheses require collected evidence")
        if len(self.hypotheses) >= self.budget.max_hypotheses:
            raise RuntimeError("hypothesis budget exhausted")
        if not hypothesis.hypothesis_id or not hypothesis.statement or not hypothesis.affected_services:
            raise ValueError("hypothesis identity, statement, and affected services are required")
        if set(hypothesis.supporting + hypothesis.refuting) - set(self.evidence):
            raise ValueError("hypothesis cites unknown evidence")
        self.hypotheses[hypothesis.hypothesis_id] = hypothesis
        self.stage = DiagnosticStage.HYPOTHESIS_TESTING

    def critic_review(self, review: CriticReview) -> None:
        if self.stage != DiagnosticStage.HYPOTHESIS_TESTING:
            raise ValueError("critic review requires hypotheses")
        if not review.reason:
            raise ValueError("critic reason is required")
        if set(review.accepted_hypotheses + review.rejected_hypotheses) - set(self.hypotheses):
            raise ValueError("critic references unknown hypothesis")
        if set(review.accepted_hypotheses) & set(review.rejected_hypotheses):
            raise ValueError("critic cannot both accept and reject a hypothesis")
        self._critic = review
        self.stage = DiagnosticStage.CRITIC_REVIEW

    def finalize(self) -> DiagnosisReport:
        if self.stage != DiagnosticStage.CRITIC_REVIEW or self._critic is None:
            raise ValueError("critic review is required before finalization")
        accepted = set(self._critic.accepted_hypotheses)
        ranked: list[RootCause] = []
        for hypothesis in self.hypotheses.values():
            if hypothesis.hypothesis_id not in accepted or not hypothesis.supporting:
                continue
            citations = tuple(self.evidence[item].citation for item in hypothesis.supporting)
            confidence = hypothesis.score()
            ranked.append(RootCause(
                hypothesis.hypothesis_id, hypothesis.statement, confidence,
                1.0 - confidence, hypothesis.affected_services, citations,
            ))
        ranked.sort(key=lambda cause: (-cause.score, cause.hypothesis_id))
        ranked = ranked[: self.budget.max_root_causes]
        if not ranked:
            self.stage = DiagnosticStage.ABSTAINED
            return DiagnosisReport(
                self.stage, (), True, self._missing_sources(), self.tool_calls, ()
            )
        self.stage = DiagnosticStage.COMPLETE
        return DiagnosisReport(
            self.stage, tuple(ranked), False, self._missing_sources(), self.tool_calls,
            tuple(citation for cause in ranked for citation in cause.citations),
        )

    def _missing_sources(self) -> tuple[str, ...]:
        if self.plan is None:
            return ()
        present = {item.source for item in self.evidence.values()}
        return tuple(source for source in self.plan.required_sources if source not in present)
