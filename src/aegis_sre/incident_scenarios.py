"""Deterministic, namespace-scoped incident scenario and injection contracts."""

from __future__ import annotations

import hashlib
import json
import random
import re
import time
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Protocol


class FaultMode(StrEnum):
    POD_CRASH = "pod_crash"
    NETWORK_LATENCY = "network_latency"
    NETWORK_ERROR = "network_error"
    CPU_STRESS = "cpu_stress"
    MEMORY_STRESS = "memory_stress"
    DNS_FAILURE = "dns_failure"
    DEPENDENCY_OUTAGE = "dependency_outage"


class RunState(StrEnum):
    CREATED = "created"
    INJECTED = "injected"
    STOPPED = "stopped"
    CLEANED = "cleaned"
    FAILED = "failed"


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    mode: FaultMode
    namespace: str
    target_service: str
    duration_seconds: float
    seed: int
    blast_radius: int
    expected_symptoms: tuple[str, ...]
    recovery_signals: tuple[str, ...]
    parameters: dict[str, float]

    def validate(self) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", self.scenario_id):
            raise ValueError("invalid scenario ID")
        if self.namespace != "aegis-lab":
            raise PermissionError("faults are restricted to aegis-lab")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", self.target_service):
            raise ValueError("invalid target service")
        if not 0 < self.duration_seconds <= 900:
            raise ValueError("duration must be between 1 and 900 seconds")
        if self.seed < 0 or not 1 <= self.blast_radius <= 3:
            raise ValueError("invalid seed or blast radius")
        if not self.expected_symptoms or not self.recovery_signals:
            raise ValueError("expected symptoms and recovery signals are required")
        if any(value < 0 for value in self.parameters.values()):
            raise ValueError("fault parameters must be non-negative")

    def manifest_hash(self) -> str:
        self.validate()
        return hashlib.sha256(
            json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


@dataclass(frozen=True)
class GroundTruth:
    injection_started_at: float
    detection_at: float | None
    recovery_at: float | None
    cleanup_at: float | None

    def validate(self) -> None:
        if self.detection_at is not None and self.detection_at < self.injection_started_at:
            raise ValueError("detection cannot precede injection")
        if self.recovery_at is not None and self.detection_at is not None and self.recovery_at < self.detection_at:
            raise ValueError("recovery cannot precede detection")
        if self.cleanup_at is not None and self.recovery_at is not None and self.cleanup_at < self.recovery_at:
            raise ValueError("cleanup cannot precede recovery")


@dataclass(frozen=True)
class ScenarioRun:
    run_id: str
    scenario: ScenarioSpec
    state: RunState
    ground_truth: GroundTruth
    injection_parameters: dict[str, float]
    error: str | None = None


class FaultAdapter(Protocol):
    def inject(self, scenario: ScenarioSpec, parameters: dict[str, float]) -> None:
        ...

    def stop(self, scenario: ScenarioSpec) -> None:
        ...

    def cleanup(self, scenario: ScenarioSpec) -> None:
        ...


def deterministic_parameters(spec: ScenarioSpec) -> dict[str, float]:
    spec.validate()
    rng = random.Random(spec.seed)
    values = dict(spec.parameters)
    if spec.mode == FaultMode.NETWORK_LATENCY:
        values.setdefault("latency_ms", float(rng.randint(50, 500)))
    elif spec.mode == FaultMode.NETWORK_ERROR:
        values.setdefault("error_rate", round(rng.uniform(0.05, 0.5), 4))
    elif spec.mode in {FaultMode.CPU_STRESS, FaultMode.MEMORY_STRESS}:
        values.setdefault("load_percent", float(rng.randint(20, 80)))
    return values


class ScenarioController:
    def start(self, spec: ScenarioSpec, adapter: FaultAdapter, *, run_id: str) -> ScenarioRun:
        spec.validate()
        if not run_id:
            raise ValueError("run_id is required")
        params = deterministic_parameters(spec)
        started = time.time()
        try:
            adapter.inject(spec, params)
        except Exception as exc:
            failure = GroundTruth(started, None, None, None)
            return ScenarioRun(run_id, spec, RunState.FAILED, failure, params, str(exc))
        return ScenarioRun(
            run_id, spec, RunState.INJECTED,
            GroundTruth(started, None, None, None), params,
        )

    def stop(self, run: ScenarioRun, adapter: FaultAdapter, *, detected_at: float | None = None) -> ScenarioRun:
        if run.state != RunState.INJECTED:
            raise ValueError("only injected runs may stop")
        now = time.time()
        detection = detected_at if detected_at is not None else now
        if detection < run.ground_truth.injection_started_at:
            raise ValueError("detection time precedes injection")
        try:
            adapter.stop(run.scenario)
            truth = GroundTruth(run.ground_truth.injection_started_at, detection, now, None)
            return ScenarioRun(run.run_id, run.scenario, RunState.STOPPED, truth, run.injection_parameters)
        except Exception as exc:
            return ScenarioRun(run.run_id, run.scenario, RunState.FAILED, run.ground_truth, run.injection_parameters, str(exc))

    def cleanup(self, run: ScenarioRun, adapter: FaultAdapter) -> ScenarioRun:
        if run.state not in {RunState.STOPPED, RunState.FAILED}:
            raise ValueError("cleanup requires a stopped or failed run")
        try:
            adapter.cleanup(run.scenario)
            truth = GroundTruth(
                run.ground_truth.injection_started_at,
                run.ground_truth.detection_at,
                run.ground_truth.recovery_at,
                time.time(),
            )
            truth.validate()
            return ScenarioRun(run.run_id, run.scenario, RunState.CLEANED, truth, run.injection_parameters, run.error)
        except Exception as exc:
            return ScenarioRun(run.run_id, run.scenario, RunState.FAILED, run.ground_truth, run.injection_parameters, str(exc))


def scenario_catalog() -> tuple[ScenarioSpec, ...]:
    common = ("error-rate increase", "latency increase")
    recovery = ("health restored", "error rate normal")
    return tuple(
        ScenarioSpec(
            scenario_id=mode.value,
            mode=mode,
            namespace="aegis-lab",
            target_service="checkout",
            duration_seconds=60.0,
            seed=index,
            blast_radius=1,
            expected_symptoms=common,
            recovery_signals=recovery,
            parameters={},
        )
        for index, mode in enumerate(FaultMode, start=1)
    )
