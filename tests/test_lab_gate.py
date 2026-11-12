from __future__ import annotations

import pytest


def manifest():
    from aegis_sre.lab_gate import LabManifest

    return LabManifest("lab-v1", "scenarios-v1", "truth-v1", "features-v1", "dataset-sha", "quality-sha", "env-v1")


def scenario(status="passed", match=True, quality=True, limitations=()):
    from aegis_sre.lab_gate import ReproductionStatus, ScenarioEvidence

    return ScenarioEvidence("s1", "run-1", "repro-sha", ReproductionStatus(status), match, quality, True, {"latency": 1.0}, limitations)


def report(scenarios):
    from aegis_sre.lab_gate import LabReport

    return LabReport(manifest(), tuple(scenarios), ("known limitation",), ("novel scenario",))


def test_gate_requires_two_approvals_and_passed_reproduction() -> None:
    current = report((scenario(),))
    assert not current.ready_for_modeling(("Karthik", "Trivedi"))
    current = current.approve("Karthik", "clean rerun").approve("Trivedi", "independent rerun")
    assert current.ready_for_modeling(("Karthik", "Trivedi"))


def test_failed_or_mismatched_scenario_blocks_gate() -> None:
    current = report((scenario(status="failed", match=False, quality=False, limitations=("missing signal",)),))
    current = current.approve("Karthik", "review").approve("Trivedi", "review")
    assert current.ready_for_modeling(("Karthik", "Trivedi")) is False


def test_quality_exception_requires_limitation() -> None:
    with pytest.raises(ValueError):
        report((scenario(quality=False),)).validate()
