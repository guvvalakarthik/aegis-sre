"""Fail-closed chaos injector with durable cleanup recovery."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ChaosPattern(StrEnum):
    POD_KILL = "pod_kill"
    NETWORK_DELAY = "network_delay"
    NETWORK_LOSS = "network_loss"
    NETWORK_PARTITION = "network_partition"
    CPU_STRESS = "cpu_stress"
    MEMORY_STRESS = "memory_stress"
    DNS_FAILURE = "dns_failure"
    DISK_PRESSURE = "disk_pressure"


@dataclass(frozen=True)
class InjectionRequest:
    injection_id: str
    cluster: str
    namespace: str
    pattern: ChaosPattern
    targets: tuple[str, ...]
    duration_seconds: float
    blast_radius: int
    parameters: dict[str, float]

    def validate(self, *, max_targets: int = 3, max_duration: float = 900.0) -> None:
        if self.cluster != "aegis-lab" or self.namespace != "aegis-lab":
            raise PermissionError("injection is restricted to the aegis-lab cluster and namespace")
        if not self.injection_id or not self.targets or len(self.targets) > max_targets:
            raise ValueError("invalid injection identity or target count")
        if not 0 < self.duration_seconds <= max_duration:
            raise ValueError("injection duration exceeds safety bound")
        if not 1 <= self.blast_radius <= max_targets:
            raise ValueError("invalid blast radius")
        if self.blast_radius < len(self.targets):
            raise ValueError("blast radius must cover declared targets")
        if any(value < 0 for value in self.parameters.values()):
            raise ValueError("injection parameters must be non-negative")


class ChaosAdapter(Protocol):
    def apply(self, request: InjectionRequest) -> None:
        ...

    def rollback(self, request: InjectionRequest) -> None:
        ...


class CleanupJournal(Protocol):
    def register(self, request: InjectionRequest, expires_at: float) -> None:
        ...

    def remove(self, injection_id: str) -> None:
        ...

    def active(self) -> tuple[tuple[InjectionRequest, float], ...]:
        ...


class MemoryCleanupJournal:
    def __init__(self) -> None:
        self._active: dict[str, tuple[InjectionRequest, float]] = {}

    def register(self, request: InjectionRequest, expires_at: float) -> None:
        self._active[request.injection_id] = (request, expires_at)

    def remove(self, injection_id: str) -> None:
        self._active.pop(injection_id, None)

    def active(self) -> tuple[tuple[InjectionRequest, float], ...]:
        return tuple(self._active.values())


class SafeInjector:
    def __init__(self, journal: CleanupJournal, *, max_active: int = 3) -> None:
        if max_active < 1:
            raise ValueError("max_active must be positive")
        self.journal = journal
        self.max_active = max_active

    def preflight(self, request: InjectionRequest, *, active_targets: set[str]) -> None:
        request.validate()
        if len(self.journal.active()) >= self.max_active:
            raise RuntimeError("active injection quota exhausted")
        if set(request.targets) & active_targets:
            raise RuntimeError("target already has an active injection")

    def start(self, request: InjectionRequest, adapter: ChaosAdapter, *, active_targets: set[str]) -> None:
        self.preflight(request, active_targets=active_targets)
        expires_at = time.time() + request.duration_seconds
        self.journal.register(request, expires_at)
        try:
            adapter.apply(request)
        except Exception:
            self.journal.remove(request.injection_id)
            raise

    def stop(self, request: InjectionRequest, adapter: ChaosAdapter) -> None:
        try:
            adapter.rollback(request)
        finally:
            self.journal.remove(request.injection_id)

    def recover_cleanup(self, adapter: ChaosAdapter, *, now: float | None = None) -> tuple[str, ...]:
        current = time.time() if now is None else now
        cleaned: list[str] = []
        for request, expires_at in self.journal.active():
            if expires_at <= current:
                try:
                    adapter.rollback(request)
                finally:
                    self.journal.remove(request.injection_id)
                cleaned.append(request.injection_id)
        return tuple(cleaned)
