from __future__ import annotations

import pytest


def operation():
    from aegis_sre.remediation_agents import RemediationOperation

    return RemediationOperation(
        "restart",
        frozenset({"dependency-timeout"}),
        lambda _: "accepted",
        lambda _: "rolled back",
    )


def plan():
    from aegis_sre.remediation_agents import RemediationPlan

    return RemediationPlan(
        "p1", "dependency-timeout", "restart",
        ("preflight healthy",), "restore latency", "medium", "one pod",
        ("health", "slo", "recurrence"), "restore prior replica count", {},
    )


def evidence(ok: bool):
    from aegis_sre.remediation_agents import VerificationEvidence

    return VerificationEvidence(ok, ok, ok, ok, "2026-01-01T00:00:00Z", ("e1",))


def test_missing_rollback_or_unsupported_cause_is_rejected() -> None:
    from aegis_sre.remediation_agents import RemediationController, RemediationPlan

    controller = RemediationController((operation(),))
    with pytest.raises(ValueError):
        controller.approve(RemediationPlan(
            "p1", "unknown", "restart", ("preflight",), "effect", "low", "canary",
            ("health",), "", {},
        ))


def test_recovery_requires_all_verification_signals() -> None:
    from aegis_sre.remediation_agents import RemediationController, RemediationStatus

    controller = RemediationController((operation(),))
    approved = controller.approve(plan())
    executed, _ = controller.execute(approved)
    rolled_back, result = controller.verify_or_recover(executed, evidence(False))
    assert rolled_back.status == RemediationStatus.ROLLED_BACK
    assert result == "rolled back"


def test_command_success_does_not_equal_recovery() -> None:
    from aegis_sre.remediation_agents import RemediationController, RemediationStatus

    controller = RemediationController((operation(),))
    executed, _ = controller.execute(controller.approve(plan()))
    verified, _ = controller.verify_or_recover(executed, evidence(True))
    assert verified.status == RemediationStatus.VERIFIED
