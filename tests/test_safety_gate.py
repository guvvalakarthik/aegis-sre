from __future__ import annotations

import pytest


def manifest():
    from aegis_sre.safety_gate import FrozenManifest

    return FrozenManifest("agent-v1", "prompt-v1", "policy-v1", ("tool-v1",), ("model-v1",))


def result(kind="read_only", outcome="completed", side_effects=0, unsafe=0):
    from aegis_sre.safety_gate import ScenarioKind, ScenarioOutcome, ScenarioResult

    return ScenarioResult(
        "s1", ScenarioKind(kind), ScenarioOutcome(outcome), unsafe, side_effects,
        side_effects, side_effects, 0.8, 0.7, 10.0, 0.1, 0, "none", True,
    )


def test_unsafe_or_unaudited_side_effects_fail_closed() -> None:
    from aegis_sre.safety_gate import SafetyReport

    SafetyReport(manifest(), (result(side_effects=1),)).validate()
    unaudited = result(side_effects=1)
    object.__setattr__(unaudited, "authorized_side_effects", 0)
    with pytest.raises(ValueError):
        SafetyReport(manifest(), (unaudited,)).validate()
    with pytest.raises(ValueError):
        SafetyReport(manifest(), (result(unsafe=1),)).validate()


def test_two_approvals_are_required_for_release() -> None:
    from aegis_sre.safety_gate import SafetyReport

    report = SafetyReport(manifest(), (result(),))
    assert not report.release_ready(("Karthik", "Trivedi"))
    report = report.approve("Karthik", "reviewed").approve("Trivedi", "reproduced")
    assert report.release_ready(("Karthik", "Trivedi"))


def test_denied_and_escalated_scenarios_have_no_side_effects() -> None:
    from aegis_sre.safety_gate import SafetyReport

    report = SafetyReport(manifest(), (result("deny", "denied"), result("approval_required", "escalated")))
    report.validate()
    assert report.failure_analysis() == ()


def test_failure_analysis_redacts_secrets() -> None:
    from aegis_sre.safety_gate import SafetyReport, ScenarioKind, ScenarioOutcome, ScenarioResult

    failed = ScenarioResult("bad", ScenarioKind.LOW_RISK, ScenarioOutcome.FAILED, 0, 0, 0, 0, None, None, 10, 0, 1, "token=secret-value", True)
    report = SafetyReport(manifest(), (failed,))
    assert report.failure_analysis() == ("token=<REDACTED>",)
