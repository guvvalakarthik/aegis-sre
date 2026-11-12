"""Evidence-first benchmark and champion-selection contracts."""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class BenchmarkSpec:
    benchmark_version: str
    dataset_version: str
    split_hash: str
    evaluation_version: str
    incident_window: str
    tasks: tuple[str, ...]
    latency_budget_ms: float
    memory_budget_mb: float
    cost_budget: float


@dataclass(frozen=True)
class BenchmarkResult:
    model: str
    task: str
    status: str
    artifact_url: str
    dataset_version: str
    split_hash: str
    metrics: dict[str, float]
    latency_ms: float | None
    memory_mb: float | None
    cost: float | None
    weaknesses: tuple[str, ...] = ()

    def validate_against(self, spec: BenchmarkSpec) -> None:
        if self.status not in {"passed", "failed", "inconclusive"}:
            raise ValueError("invalid benchmark status")
        if not self.artifact_url.startswith(("http://", "https://")):
            raise ValueError("machine-generated artifact URL is required")
        if (self.dataset_version, self.split_hash) != (spec.dataset_version, spec.split_hash):
            raise ValueError("result lineage does not match benchmark spec")
        if not self.metrics and self.status == "passed":
            raise ValueError("passed results require metrics")
        if any(not math.isfinite(value) for value in self.metrics.values()):
            raise ValueError("metrics must be finite")
        for value in (self.latency_ms, self.memory_mb, self.cost):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError("operational measurements must be finite and non-negative")


@dataclass(frozen=True)
class Approval:
    contributor: str
    rationale_hash: str


@dataclass(frozen=True)
class BenchmarkReport:
    spec: BenchmarkSpec
    results: tuple[BenchmarkResult, ...]
    approvals: tuple[Approval, ...] = ()

    def validate(self) -> None:
        if not self.results:
            raise ValueError("benchmark report cannot be empty")
        for result in self.results:
            result.validate_against(self.spec)
        if len({(result.model, result.task) for result in self.results}) != len(self.results):
            raise ValueError("duplicate model/task result")

    def approve(self, contributor: str, rationale: str) -> "BenchmarkReport":
        self.validate()
        if not contributor or not rationale:
            raise ValueError("approval identity and rationale are required")
        approval = Approval(
            contributor=contributor,
            rationale_hash=hashlib.sha256(rationale.encode()).hexdigest(),
        )
        existing = tuple(item for item in self.approvals if item.contributor != contributor)
        return BenchmarkReport(self.spec, self.results, existing + (approval,))

    def independently_approved(self, required: Sequence[str]) -> bool:
        return set(required).issubset({approval.contributor for approval in self.approvals})

    def to_json(self) -> str:
        self.validate()
        return json.dumps(asdict(self), sort_keys=True, indent=2)


def select_champions(
    report: BenchmarkReport,
    *,
    metric: str,
    required_approvals: Sequence[str],
) -> dict[str, tuple[str, str | None]]:
    """Select a champion and fallback only after lineage, budgets, and approvals pass."""
    report.validate()
    if not report.independently_approved(required_approvals):
        raise ValueError("independent approvals are required before selection")
    selected: dict[str, tuple[str, str | None]] = {}
    for task in report.spec.tasks:
        eligible = [
            result for result in report.results
            if result.task == task
            and result.status == "passed"
            and metric in result.metrics
            and result.latency_ms is not None
            and result.latency_ms <= report.spec.latency_budget_ms
            and result.memory_mb is not None
            and result.memory_mb <= report.spec.memory_budget_mb
            and result.cost is not None
            and result.cost <= report.spec.cost_budget
        ]
        eligible.sort(key=lambda result: result.metrics[metric], reverse=True)
        if not eligible:
            selected[task] = ("unavailable", None)
        else:
            selected[task] = (eligible[0].model, eligible[1].model if len(eligible) > 1 else None)
    return selected


def confidence_interval(
    values: Sequence[float],
    *,
    seed: int = 42,
    samples: int = 2000,
    confidence: float = 0.95,
) -> tuple[float, float, float]:
    if not values or samples < 100 or not 0.0 < confidence < 1.0:
        raise ValueError("invalid confidence interval configuration")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("values must be finite")
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(samples))
    alpha = (1.0 - confidence) / 2.0
    return (
        sum(values) / len(values),
        means[int(alpha * samples)],
        means[min(samples - 1, int((1.0 - alpha) * samples))],
    )


def false_alarm_impact(
    false_alarms: int,
    observation_windows: int,
    *,
    intervention_cost: float,
) -> float:
    if false_alarms < 0 or observation_windows <= 0 or intervention_cost < 0:
        raise ValueError("invalid false-alarm inputs")
    return false_alarms / observation_windows * intervention_cost
