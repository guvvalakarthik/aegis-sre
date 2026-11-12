"""Fail-closed incident state machine and least-privilege typed tool runtime."""

from __future__ import annotations

import copy
import re
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Mapping, Protocol


class IncidentState(StrEnum):
    CREATED = "created"
    INVESTIGATING = "investigating"
    AWAITING_APPROVAL = "awaiting_approval"
    REMEDIATING = "remediating"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    FAILED = "failed"
    CANCELLED = "cancelled"


_TRANSITIONS = {
    IncidentState.CREATED: {IncidentState.INVESTIGATING, IncidentState.CANCELLED},
    IncidentState.INVESTIGATING: {IncidentState.AWAITING_APPROVAL, IncidentState.FAILED, IncidentState.CANCELLED},
    IncidentState.AWAITING_APPROVAL: {IncidentState.REMEDIATING, IncidentState.CANCELLED},
    IncidentState.REMEDIATING: {IncidentState.VERIFYING, IncidentState.FAILED, IncidentState.CANCELLED},
    IncidentState.VERIFYING: {IncidentState.RESOLVED, IncidentState.REMEDIATING, IncidentState.FAILED},
    IncidentState.RESOLVED: set(),
    IncidentState.FAILED: set(),
    IncidentState.CANCELLED: set(),
}


@dataclass(frozen=True)
class RuntimeBudget:
    max_tokens: int
    max_seconds: float
    max_tool_calls: int
    max_retries: int

    def validate(self) -> None:
        if min(self.max_tokens, self.max_tool_calls) < 1 or self.max_seconds <= 0 or self.max_retries < 0:
            raise ValueError("invalid runtime budget")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    allowed_roles: frozenset[str]
    permissions: frozenset[str]
    validator: Callable[[Mapping[str, Any]], None]
    handler: Callable[[Mapping[str, Any]], Any]
    side_effect: bool = False


class CheckpointStore(Protocol):
    def save(self, incident_id: str, checkpoint: dict[str, Any]) -> None:
        ...

    def load(self, incident_id: str) -> dict[str, Any] | None:
        ...


class MemoryCheckpointStore:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    def save(self, incident_id: str, checkpoint: dict[str, Any]) -> None:
        self._items[incident_id] = copy.deepcopy(checkpoint)

    def load(self, incident_id: str) -> dict[str, Any] | None:
        value = self._items.get(incident_id)
        return copy.deepcopy(value) if value is not None else None


@dataclass
class IncidentRuntime:
    incident_id: str
    store: CheckpointStore
    budget: RuntimeBudget
    state: IncidentState = IncidentState.CREATED
    version: int = 0
    tokens_used: int = 0
    tool_calls: int = 0
    retries_used: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    idempotency_results: dict[str, Any] = field(default_factory=dict)
    failures: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.budget.validate()
        self._commit("created", {"state": self.state.value})

    def _commit(self, event: str, payload: dict[str, Any]) -> None:
        self.version += 1
        self.events.append({
            "version": self.version,
            "event": event,
            "payload": _redact(payload),
            "timestamp": time.time(),
        })
        self.store.save(self.incident_id, self.checkpoint())

    def checkpoint(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "state": self.state.value,
            "version": self.version,
            "tokens_used": self.tokens_used,
            "tool_calls": self.tool_calls,
            "retries_used": self.retries_used,
            "events": copy.deepcopy(self.events),
            "idempotency_results": copy.deepcopy(self.idempotency_results),
            "failures": copy.deepcopy(self.failures),
        }

    def transition(self, target: IncidentState, *, reason: str) -> None:
        if target not in _TRANSITIONS[self.state]:
            raise ValueError(f"invalid transition {self.state.value}->{target.value}")
        if not reason:
            raise ValueError("transition reason is required")
        previous = self.state
        self.state = target
        self._commit("transition", {"from": previous.value, "to": target.value, "reason": reason})

    def consume_tokens(self, count: int) -> None:
        if count < 0 or self.tokens_used + count > self.budget.max_tokens:
            raise RuntimeError("token budget exhausted")
        self.tokens_used += count
        self._commit("budget", {"tokens_used": self.tokens_used})

    def execute_tool(
        self,
        spec: ToolSpec,
        arguments: Mapping[str, Any],
        *,
        actor_roles: frozenset[str],
        idempotency_key: str,
        timeout_seconds: float = 10.0,
    ) -> Any:
        if not idempotency_key:
            raise ValueError("idempotency key is required")
        if self.state in {IncidentState.RESOLVED, IncidentState.FAILED, IncidentState.CANCELLED}:
            raise RuntimeError("terminal incident cannot execute tools")
        if not spec.name or not spec.allowed_roles or not actor_roles.intersection(spec.allowed_roles):
            raise PermissionError("tool authorization denied")
        if {"shell", "cluster-admin", "unrestricted"} & spec.permissions:
            raise PermissionError("forbidden tool permission")
        if timeout_seconds <= 0 or timeout_seconds > self.budget.max_seconds:
            raise ValueError("invalid tool timeout")
        if idempotency_key in self.idempotency_results:
            return copy.deepcopy(self.idempotency_results[idempotency_key])
        spec.validator(arguments)
        if self.tool_calls >= self.budget.max_tool_calls:
            raise RuntimeError("tool-call budget exhausted")
        failure_count = self.failures.get(spec.name, 0)
        if failure_count >= 3:
            raise RuntimeError("tool circuit breaker is open")
        self.tool_calls += 1
        self._commit("tool_started", {"tool": spec.name, "idempotency_key": idempotency_key})
        last_error: Exception | None = None
        for attempt in range(self.budget.max_retries + 1):
            if attempt:
                self.retries_used += 1
                if self.retries_used > self.budget.max_retries:
                    break
            started = time.monotonic()
            try:
                result = spec.handler(arguments)
                if time.monotonic() - started > timeout_seconds:
                    raise TimeoutError("tool timeout exceeded")
                safe_result = _redact(result)
                self.idempotency_results[idempotency_key] = safe_result
                self.failures.pop(spec.name, None)
                self._commit("tool_completed", {"tool": spec.name, "result": safe_result})
                return copy.deepcopy(safe_result)
            except Exception as exc:
                last_error = exc
                self.failures[spec.name] = failure_count + attempt + 1
                self._commit("tool_failed", {"tool": spec.name, "attempt": attempt + 1, "error": str(exc)})
        raise RuntimeError(f"tool failed: {spec.name}") from last_error

    @classmethod
    def resume(cls, incident_id: str, store: CheckpointStore, budget: RuntimeBudget) -> "IncidentRuntime":
        checkpoint = store.load(incident_id)
        if checkpoint is None:
            raise KeyError("checkpoint not found")
        runtime = cls.__new__(cls)
        runtime.incident_id = incident_id
        runtime.store = store
        runtime.budget = budget
        runtime.state = IncidentState(checkpoint["state"])
        runtime.version = checkpoint["version"]
        runtime.tokens_used = checkpoint["tokens_used"]
        runtime.tool_calls = checkpoint["tool_calls"]
        runtime.retries_used = checkpoint["retries_used"]
        runtime.events = checkpoint["events"]
        runtime.idempotency_results = checkpoint["idempotency_results"]
        runtime.failures = checkpoint["failures"]
        return runtime


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(
            r"(?i)(password|secret|token|api[_-]?key|authorization)\s*[:=]\s*[^\s,;]+",
            r"\1=<REDACTED>",
            value,
        )
    if isinstance(value, Mapping):
        return {str(key): _redact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value
