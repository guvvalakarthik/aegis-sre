"""Typed, bounded fault-injection orchestration without shell execution."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Event, Lock
from typing import Any, Protocol


class FaultAdapter(Protocol):
    """Adapter contract for one registered, typed fault operation."""

    def apply(self, target: str, parameters: dict[str, Any]) -> dict[str, Any]:
        ...

    def rollback(self, target: str, state: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class FaultRequest:
    operation: str
    target: str
    parameters: dict[str, Any]
    idempotency_key: str
    timeout_seconds: int = 60


@dataclass(frozen=True)
class AuditEvent:
    event: str
    idempotency_key: str
    operation: str
    target: str
    occurred_at: datetime
    details: dict[str, Any]


@dataclass(frozen=True)
class FaultResult:
    status: str
    idempotency_key: str
    operation: str
    target: str
    before: dict[str, Any]
    after: dict[str, Any]
    cleanup: dict[str, Any] | None


class FaultEngine:
    """Run only registered adapters with a target lock, deadline, and kill switch."""

    def __init__(self, adapters: dict[str, FaultAdapter], *, max_timeout_seconds: int = 300) -> None:
        self._adapters = dict(adapters)
        self._max_timeout_seconds = max_timeout_seconds
        self._locks: dict[str, Lock] = {}
        self._locks_guard = Lock()
        self._kill_switch = Event()
        self._runs: dict[str, FaultResult] = {}
        self.audit: list[AuditEvent] = []

    def stop(self) -> None:
        """Stop new operations and cause the current operation to enter cleanup."""
        self._kill_switch.set()

    def reset_stop(self) -> None:
        self._kill_switch.clear()

    def _target_lock(self, target: str) -> Lock:
        with self._locks_guard:
            return self._locks.setdefault(target, Lock())

    def _record(self, event: str, request: FaultRequest, **details: Any) -> None:
        self.audit.append(
            AuditEvent(
                event=event,
                idempotency_key=request.idempotency_key,
                operation=request.operation,
                target=request.target,
                occurred_at=datetime.now(timezone.utc),
                details=details,
            )
        )

    def cleanup(self, request: FaultRequest, state: dict[str, Any]) -> dict[str, Any]:
        """Rollback a registered operation; repeated cleanup is safe by contract."""
        adapter = self._adapters[request.operation]
        self._record("cleanup_started", request)
        try:
            result = self._run_with_timeout(
                lambda: adapter.rollback(request.target, state),
                request.timeout_seconds,
            )
        except Exception as exc:
            self._record("cleanup_failed", request, error=type(exc).__name__)
            raise
        self._record("cleanup_succeeded", request, result=result)
        return result

    def execute(self, request: FaultRequest, *, dry_run: bool = False) -> FaultResult:
        if request.operation not in self._adapters:
            raise ValueError("operation is not registered")
        if not request.target:
            raise ValueError("target is required")
        if not request.idempotency_key:
            raise ValueError("idempotency_key is required")
        if not 0 < request.timeout_seconds <= self._max_timeout_seconds:
            raise ValueError("timeout exceeds engine safety limit")
        if request.idempotency_key in self._runs:
            return self._runs[request.idempotency_key]
        if self._kill_switch.is_set():
            raise RuntimeError("fault engine kill switch is active")

        lock = self._target_lock(request.target)
        if not lock.acquire(blocking=False):
            raise RuntimeError("target is already reserved by another experiment")

        adapter = self._adapters[request.operation]
        self._record("run_started", request, dry_run=dry_run)
        state: dict[str, Any] = {}
        cleanup_result: dict[str, Any] | None = None
        try:
            if dry_run:
                result = FaultResult("planned", request.idempotency_key, request.operation, request.target, {}, {}, None)
                self._record("run_planned", request)
                self._runs[request.idempotency_key] = result
                return result
            if self._kill_switch.is_set():
                raise RuntimeError("fault engine kill switch is active")
            state = self._run_with_timeout(
                lambda: adapter.apply(request.target, request.parameters),
                request.timeout_seconds,
            )
            self._record("fault_applied", request, state=state)
            if self._kill_switch.is_set():
                raise RuntimeError("fault engine kill switch activated during run")
            result = FaultResult("succeeded", request.idempotency_key, request.operation, request.target, {}, state, None)
            self._runs[request.idempotency_key] = result
            return result
        except Exception as exc:
            self._record("run_failed", request, error=type(exc).__name__)
            if state:
                cleanup_result = self.cleanup(request, state)
            result = FaultResult("failed", request.idempotency_key, request.operation, request.target, {}, state, cleanup_result)
            self._runs[request.idempotency_key] = result
            return result
        finally:
            lock.release()

    @staticmethod
    def _run_with_timeout(function: Any, timeout_seconds: int) -> dict[str, Any]:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(function)
            try:
                result = future.result(timeout=timeout_seconds)
            except TimeoutError as exc:
                future.cancel()
                raise TimeoutError("fault operation exceeded its deadline") from exc
        if not isinstance(result, dict):
            raise TypeError("fault adapter returned a non-object result")
        return result
