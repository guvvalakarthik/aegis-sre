from __future__ import annotations

import pytest


class Adapter:
    def __init__(self):
        self.applied = []
        self.rolled_back = []

    def apply(self, request): self.applied.append(request.injection_id)
    def rollback(self, request): self.rolled_back.append(request.injection_id)


def request(namespace="aegis-lab", cluster="aegis-lab", injection_id="i1"):
    from aegis_sre.safe_fault_injection import ChaosPattern, InjectionRequest

    return InjectionRequest(injection_id, cluster, namespace, ChaosPattern.POD_KILL, ("checkout",), 10.0, 1, {})


def test_out_of_scope_injection_is_rejected() -> None:
    from aegis_sre.safe_fault_injection import MemoryCleanupJournal, SafeInjector

    with pytest.raises(PermissionError):
        SafeInjector(MemoryCleanupJournal()).preflight(request(namespace="default"), active_targets=set())


def test_failed_apply_is_not_left_active() -> None:
    from aegis_sre.safe_fault_injection import MemoryCleanupJournal, SafeInjector

    class Broken:
        def apply(self, request): raise RuntimeError("apply failed")
        def rollback(self, request): pass

    journal = MemoryCleanupJournal()
    with pytest.raises(RuntimeError):
        SafeInjector(journal).start(request(), Broken(), active_targets=set())
    assert journal.active() == ()


def test_expiry_cleanup_recovers_after_restart() -> None:
    from aegis_sre.safe_fault_injection import MemoryCleanupJournal, SafeInjector

    journal = MemoryCleanupJournal()
    injector = SafeInjector(journal)
    adapter = Adapter()
    injector.start(request(), adapter, active_targets=set())
    assert injector.recover_cleanup(adapter, now=1e20) == ("i1",)
    assert adapter.rolled_back == ["i1"]
    assert journal.active() == ()


def test_overlapping_targets_are_blocked() -> None:
    from aegis_sre.safe_fault_injection import MemoryCleanupJournal, SafeInjector

    with pytest.raises(RuntimeError, match="active"):
        SafeInjector(MemoryCleanupJournal()).preflight(request(), active_targets={"checkout"})
