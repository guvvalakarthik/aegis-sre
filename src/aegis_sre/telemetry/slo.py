"""SLO definitions and deterministic calculations from telemetry aggregates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SLO:
    name: str
    target: float
    unit: str
    description: str


SLOS = (
    SLO("availability", 0.999, "ratio", "successful requests / total requests"),
    SLO("latency_p95_ms", 500.0, "milliseconds", "95th percentile request latency"),
    SLO("error_rate", 0.001, "ratio", "failed requests / total requests"),
    SLO("saturation", 0.80, "ratio", "resource utilization ceiling"),
    SLO("detection_latency_seconds", 60.0, "seconds", "incident signal to detection"),
    SLO("recovery_time_seconds", 300.0, "seconds", "detection to recovered service"),
)


def ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    return numerator / denominator


def availability(successful: int, total: int) -> float:
    return ratio(successful, total)


def error_rate(failed: int, total: int) -> float:
    return ratio(failed, total)


def percentile(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered or not 0 <= quantile <= 1:
        raise ValueError("values must be non-empty and quantile must be between 0 and 1")
    index = min(len(ordered) - 1, int((len(ordered) - 1) * quantile))
    return ordered[index]


def meets_lower_bound(value: float, target: float) -> bool:
    return value >= target


def meets_upper_bound(value: float, target: float) -> bool:
    return value <= target
