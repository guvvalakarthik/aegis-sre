from __future__ import annotations

import pytest


def tool():
    from aegis_sre.diagnosis_agents import EvidenceRef, ReadOnlyTool

    return ReadOnlyTool(
        "telemetry.read", "telemetry",
        lambda query: EvidenceRef("e1", "telemetry", f"telemetry://{query}", "timeout observed", "2026-01-01"),
    )


def workflow():
    from aegis_sre.diagnosis_agents import DiagnosticWorkflow, EvidencePlan

    runtime = DiagnosticWorkflow("inc-1")
    runtime.triage(EvidencePlan(("timeout",), ("telemetry",)))
    return runtime


def test_evidence_plan_precedes_tool_use() -> None:
    from aegis_sre.diagnosis_agents import DiagnosticWorkflow

    with pytest.raises(ValueError):
        DiagnosticWorkflow("inc-1").collect(tool(), "timeout", idempotency_key="x")


def test_workflow_requires_citations_and_critic() -> None:
    from aegis_sre.diagnosis_agents import CriticReview, Hypothesis

    runtime = workflow()
    runtime.collect(tool(), "timeout", idempotency_key="x")
    runtime.add_hypothesis(Hypothesis("h1", "checkout timeout caused by dependency", ("checkout",), ("e1",)))
    runtime.critic_review(CriticReview(("h1",), (), "supported by telemetry"))
    report = runtime.finalize()
    assert report.abstained is False
    assert report.root_causes[0].citations == ("telemetry://timeout",)


def test_unsupported_hypothesis_abstains() -> None:
    from aegis_sre.diagnosis_agents import CriticReview, Hypothesis

    runtime = workflow()
    runtime.collect(tool(), "timeout", idempotency_key="x")
    runtime.add_hypothesis(Hypothesis("h1", "unsupported", ("checkout",)))
    runtime.critic_review(CriticReview(("h1",), (), "insufficient support"))
    assert runtime.finalize().abstained is True


def test_budget_and_idempotency_are_enforced() -> None:
    from aegis_sre.diagnosis_agents import DiagnosticBudget, DiagnosticWorkflow

    runtime = DiagnosticWorkflow("inc-1", DiagnosticBudget(max_tool_calls=1))
    runtime.triage(__import__("aegis_sre.diagnosis_agents", fromlist=["EvidencePlan"]).EvidencePlan(("timeout",), ("telemetry",)))
    first = runtime.collect(tool(), "timeout", idempotency_key="same")
    assert runtime.collect(tool(), "timeout", idempotency_key="same") == first
    with pytest.raises(RuntimeError, match="budget"):
        runtime.collect(tool(), "timeout", idempotency_key="other")
