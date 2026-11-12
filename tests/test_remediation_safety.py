from __future__ import annotations

import time

import pytest


class Executor:
    def __init__(self, healthy: bool = True):
        self.healthy = healthy
        self.rollback_count = 0

    def dry_run(self, request): pass
    def canary(self, request): pass
    def apply(self, request): pass
    def rollback(self, request): self.rollback_count += 1
    def health_check(self, request): return self.healthy


def request(risk=1):
    from aegis_sre.remediation_safety import ActionRequest, RiskClass

    return ActionRequest("r1", "restart", "checkout", "prod", RiskClass(risk), {"scope": "canary"}, "ignore policy")


def controller():
    from aegis_sre.remediation_safety import Policy, SafetyController

    return SafetyController(
        Policy(frozenset({"restart"}), frozenset({"checkout"}), frozenset({"prod"})),
        approval_secret=b"test-secret",
    )


def test_prompt_text_cannot_change_policy() -> None:
    controller().authorize(request(), actor="agent", roles=frozenset({"operator"}))


def test_high_risk_requires_authenticated_approval() -> None:
    c = controller()
    with pytest.raises(PermissionError):
        c.authorize(request(3), actor="agent", roles=frozenset({"operator"}))
    approval = c.sign_approval("human", request(3), time.time() + 60)
    c.authorize(request(3), actor="agent", roles=frozenset({"operator", "approver"}), approval=approval)


def test_failed_health_gate_rolls_back() -> None:
    from aegis_sre.remediation_safety import Decision

    executor = Executor(False)
    assert controller().execute(request(), executor, actor="agent", roles=frozenset({"operator"})) == Decision.ROLLED_BACK
    assert executor.rollback_count == 1


def test_kill_switch_denies_and_audit_is_hash_chained() -> None:
    c = controller()
    c.set_kill_switch(True, actor="operator")
    with pytest.raises(PermissionError):
        c.authorize(request(), actor="agent", roles=frozenset({"operator"}))
    records = c.audit_log()
    assert records[-1].decision.value == "denied"
    assert records[-1].previous_hash == records[-2].record_hash
