"""Deterministic, prefix-only statistical and rule-based anomaly baselines."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Sequence


@dataclass(frozen=True)
class Detection:
    index: int
    score: float
    anomalous: bool
    window_start: int
    window_end: int


@dataclass(frozen=True)
class EvaluationMetrics:
    precision: float
    recall: float
    false_alarm_rate: float
    detection_latency: float | None


def _finite_values(values: Sequence[float]) -> list[float]:
    result = [float(value) for value in values]
    if not result or not all(math.isfinite(value) for value in result):
        raise ValueError("values must be finite and non-empty")
    return result


def calibrate_threshold(baseline: Sequence[float], *, quantile: float = 0.995) -> float:
    values = sorted(_finite_values(baseline))
    if not 0.0 < quantile < 1.0:
        raise ValueError("quantile must be between 0 and 1")
    position = min(len(values) - 1, int(quantile * len(values)))
    return values[position]


def threshold_detector(values: Sequence[float], *, threshold: float, direction: str = "above") -> tuple[Detection, ...]:
    series = _finite_values(values)
    if direction not in {"above", "below", "absolute"} or not math.isfinite(threshold):
        raise ValueError("invalid threshold detector configuration")
    results: list[Detection] = []
    for index, value in enumerate(series):
        score = value if direction != "absolute" else abs(value)
        anomalous = score > threshold if direction in {"above", "absolute"} else score < threshold
        results.append(Detection(index, score, anomalous, index, index + 1))
    return tuple(results)


def slo_detector(
    values: Sequence[float],
    *,
    objective: float,
    direction: str,
    window: int = 1,
) -> tuple[Detection, ...]:
    if window < 1 or direction not in {"max", "min"}:
        raise ValueError("invalid SLO detector configuration")
    series = _finite_values(values)
    results: list[Detection] = []
    for index in range(len(series)):
        start = max(0, index - window + 1)
        aggregate = max(series[start:index + 1]) if direction == "max" else min(series[start:index + 1])
        score = aggregate - objective if direction == "max" else objective - aggregate
        results.append(Detection(index, max(0.0, score), score > 0, start, index + 1))
    return tuple(results)


def zscore_detector(
    values: Sequence[float],
    *,
    baseline_mean: float,
    baseline_std: float,
    threshold: float = 3.0,
) -> tuple[Detection, ...]:
    series = _finite_values(values)
    if baseline_std <= 0 or threshold <= 0:
        raise ValueError("baseline standard deviation and threshold must be positive")
    return tuple(
        Detection(index, abs((value - baseline_mean) / baseline_std), abs((value - baseline_mean) / baseline_std) > threshold, index, index + 1)
        for index, value in enumerate(series)
    )


def ewma_detector(
    values: Sequence[float],
    *,
    alpha: float = 0.2,
    baseline_mean: float,
    baseline_std: float,
    threshold: float = 3.0,
) -> tuple[Detection, ...]:
    series = _finite_values(values)
    if not 0.0 < alpha <= 1.0 or baseline_std <= 0:
        raise ValueError("invalid EWMA configuration")
    state = baseline_mean
    results: list[Detection] = []
    for index, value in enumerate(series):
        state = alpha * value + (1.0 - alpha) * state
        score = abs((value - state) / baseline_std)
        results.append(Detection(index, score, score > threshold, index, index + 1))
    return tuple(results)


def holt_detector(values: Sequence[float], *, alpha: float = 0.3, beta: float = 0.1, threshold: float = 3.0) -> tuple[Detection, ...]:
    series = _finite_values(values)
    if not 0.0 < alpha <= 1.0 or not 0.0 < beta <= 1.0 or threshold <= 0:
        raise ValueError("invalid Holt configuration")
    level = series[0]
    trend = 0.0
    results = [Detection(0, 0.0, False, 0, 1)]
    for index, value in enumerate(series[1:], start=1):
        forecast = level + trend
        error = abs(value - forecast)
        level, trend = alpha * value + (1 - alpha) * forecast, beta * (level - forecast) + (1 - beta) * trend
        results.append(Detection(index, error, error > threshold, index, index + 1))
    return tuple(results)


def seasonal_detector(values: Sequence[float], *, period: int, threshold: float) -> tuple[Detection, ...]:
    series = _finite_values(values)
    if period < 1 or threshold <= 0:
        raise ValueError("invalid seasonal configuration")
    results: list[Detection] = []
    for index, value in enumerate(series):
        history = series[index - period] if index >= period else None
        score = abs(value - history) if history is not None else 0.0
        results.append(Detection(index, score, score > threshold, max(0, index - period), index + 1))
    return tuple(results)


def rule_detector(
    records: Sequence[dict[str, object]],
    rules: Sequence[Callable[[dict[str, object]], float]],
    *,
    threshold: float = 0.0,
) -> tuple[Detection, ...]:
    if not rules:
        raise ValueError("at least one rule is required")
    results: list[Detection] = []
    for index, record in enumerate(records):
        scores = [float(rule(record)) for rule in rules]
        if not all(math.isfinite(score) for score in scores):
            raise ValueError("rule scores must be finite")
        score = max(scores)
        results.append(Detection(index, score, score > threshold, index, index + 1))
    return tuple(results)


def evaluate(detections: Sequence[Detection], labels: Sequence[bool]) -> EvaluationMetrics:
    if len(detections) != len(labels) or not detections:
        raise ValueError("detections and labels must have equal non-empty lengths")
    tp = sum(item.anomalous and label for item, label in zip(detections, labels))
    fp = sum(item.anomalous and not label for item, label in zip(detections, labels))
    positives = sum(labels)
    first_positive = next((index for index, label in enumerate(labels) if label), None)
    first_detection = next((item.index for item in detections if item.anomalous), None)
    return EvaluationMetrics(
        tp / (tp + fp) if tp + fp else 0.0,
        tp / positives if positives else 0.0,
        fp / max(1, len(labels) - positives),
        float(first_detection - first_positive) if first_positive is not None and first_detection is not None else None,
    )
