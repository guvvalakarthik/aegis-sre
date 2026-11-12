from __future__ import annotations

import pytest


def test_redaction_removes_sensitive_dashboard_values() -> None:
    from aegis_sre.dashboard import redact

    assert redact({"message": "token=secret-value"})["message"] == "token=<REDACTED>"


def test_store_requires_roles_for_actions() -> None:
    from aegis_sre.dashboard import InMemoryDashboardStore, IncidentSnapshot, Principal

    snapshot = IncidentSnapshot("i1", "open", "high", "now", ("checkout",), (), (), None, ())
    store = InMemoryDashboardStore((snapshot,))
    with pytest.raises(PermissionError):
        store.request_approval("i1", Principal("viewer", frozenset({"viewer"})), "approve")
    store.request_approval("i1", Principal("approver", frozenset({"approver"})), "approve")
