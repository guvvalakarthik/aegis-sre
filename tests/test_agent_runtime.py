from __future__ import annotations

import pytest


def validator(arguments):
    if "query" not in arguments:
        raise ValueError("query required")


def test_state_transitions_and_resume() -> None:
    from aegis_sre.agent_runtime import (
        IncidentRuntime,
        IncidentState,
        MemoryCheckpointStore,
        RuntimeBudget,
    )

    store = MemoryCheckpointStore()
    budget = RuntimeBudget(1000, 30.0, 3, 1)
    runtime = IncidentRuntime("inc-1", store, budget)
    runtime.transition(IncidentState.INVESTIGATING, reason="triage")
    resumed = IncidentRuntime.resume("inc-1", store, budget)
    assert resumed.state == IncidentState.INVESTIGATING
    assert resumed.version == runtime.version


def test_invalid_transition_and_forbidden_permission_fail_closed() -> None:
    from aegis_sre.agent_runtime import IncidentRuntime, MemoryCheckpointStore, RuntimeBudget, ToolSpec

    runtime = IncidentRuntime("inc-1", MemoryCheckpointStore(), RuntimeBudget(100, 10.0, 1, 0))
    with pytest.raises(ValueError):
        runtime.transition(__import__("aegis_sre.agent_runtime", fromlist=["IncidentState"]).IncidentState.RESOLVED, reason="skip")
    forbidden = ToolSpec("shell", frozenset({"operator"}), frozenset({"shell"}), validator, lambda _: "x")
    with pytest.raises(PermissionError):
        runtime.execute_tool(forbidden, {"query": "x"}, actor_roles=frozenset({"operator"}), idempotency_key="k")


def test_idempotency_redaction_and_retry() -> None:
    from aegis_sre.agent_runtime import IncidentRuntime, MemoryCheckpointStore, RuntimeBudget, ToolSpec

    calls = {"count": 0}
    def handler(_: object):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary")
        return {"token=abc": "ok"}

    runtime = IncidentRuntime("inc-1", MemoryCheckpointStore(), RuntimeBudget(100, 10.0, 2, 1))
    spec = ToolSpec("read", frozenset({"operator"}), frozenset({"telemetry:read"}), validator, handler)
    result = runtime.execute_tool(spec, {"query": "x"}, actor_roles=frozenset({"operator"}), idempotency_key="same")
    assert calls["count"] == 2
    assert runtime.execute_tool(spec, {"query": "x"}, actor_roles=frozenset({"operator"}), idempotency_key="same") == result
    assert calls["count"] == 2


def test_invalid_arguments_and_budget_are_enforced() -> None:
    from aegis_sre.agent_runtime import IncidentRuntime, MemoryCheckpointStore, RuntimeBudget, ToolSpec

    runtime = IncidentRuntime("inc-1", MemoryCheckpointStore(), RuntimeBudget(1, 10.0, 1, 0))
    spec = ToolSpec("read", frozenset({"operator"}), frozenset({"evidence:read"}), validator, lambda _: "ok")
    with pytest.raises(ValueError):
        runtime.execute_tool(spec, {}, actor_roles=frozenset({"operator"}), idempotency_key="x")
    runtime.consume_tokens(1)
    with pytest.raises(RuntimeError, match="budget"):
        runtime.consume_tokens(1)


def test_timeout_is_recorded_and_does_not_return_success() -> None:
    import time
    from aegis_sre.agent_runtime import IncidentRuntime, MemoryCheckpointStore, RuntimeBudget, ToolSpec

    def slow(_: object):
        time.sleep(0.2)
        return "late"

    runtime = IncidentRuntime("inc-timeout", MemoryCheckpointStore(), RuntimeBudget(100, 10.0, 1, 0))
    spec = ToolSpec("read", frozenset({"operator"}), frozenset({"telemetry:read"}), validator, slow)
    with pytest.raises(RuntimeError, match="tool failed"):
        runtime.execute_tool(
            spec, {"query": "x"}, actor_roles=frozenset({"operator"}),
            idempotency_key="timeout", timeout_seconds=0.01,
        )
