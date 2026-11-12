from __future__ import annotations

import pytest


def truth():
    from aegis_sre.ground_truth import GroundTruth, Severity, TimelineEvent

    return GroundTruth(
        "latency-1", "dependency-timeout", ("checkout",), 1, Severity.HIGH,
        "restore dependency", ("healthy",), ("latency",), ("retry storm",),
        (TimelineEvent("inject", 0.0, ("e1",)), TimelineEvent("recover", 30.0, ("e2",))),
        ("run-1",),
    )


def run():
    from aegis_sre.ground_truth import ObservedRun

    return ObservedRun("run-1", "dependency-timeout", ("checkout",), 1, frozenset({"healthy"}), {"inject": 0.2, "recover": 31.0})


def test_ground_truth_matches_observed_run_within_tolerance() -> None:
    from aegis_sre.ground_truth import compare_ground_truth

    accuracy = compare_ground_truth(truth(), run(), timeline_tolerance_seconds=2)
    assert accuracy.accurate is True


def test_mismatched_root_cause_is_not_hidden() -> None:
    from aegis_sre.ground_truth import compare_ground_truth

    observed = run()
    object.__setattr__(observed, "observed_root_cause", "wrong-cause")
    assert compare_ground_truth(truth(), observed).root_cause_match is False


def test_playbook_requires_rollback_and_verified_runs() -> None:
    from aegis_sre.ground_truth import RemediationPlaybook

    playbook = RemediationPlaybook(
        "p1", "latency-1", "dependency-timeout", ("restart",),
        ("healthy before",), ("restore",), ("healthy",), ("run-1",),
    )
    playbook.verify_against(truth(), (run(),))
    with pytest.raises(ValueError):
        RemediationPlaybook("p2", "latency-1", "wrong", ("restart",), (), (), (), ()).validate()
