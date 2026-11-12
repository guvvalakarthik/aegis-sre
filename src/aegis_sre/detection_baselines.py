"""Deterministic statistical detectors and shared evaluation metrics."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev
from typing import Iterable


@dataclass(frozen=True)
class Detection:
    index: int
    score: float
    explanation: str


@dataclass(frozen=True)
class BaselineMetrics:
    precision: float
    recall: float
    f1: float
    false_alarms_per_hour: float
    mean_detection_delay: float | None


def _detection(index: int, score: float, explanation: str) -> Detection:
    return Detection(index=index, score=score, explanation=explanation)


def static_threshold(values: list[float], *, upper: float) -> list[Detection]:
    return [_detection(i, value - upper, f"value {value:.4g} exceeded threshold {upper:.4g}") for i, value in enumerate(values) if value > upper]


def rolling_zscore(values: list[float], *, window: int = 20, threshold: float = 3.0) -> list[Detection]:
    if window < 2:
        raise ValueError("window must be at least 2")
    detections: list[Detection] = []
    for index in range(window, len(values)):
        history = values[index - window:index]
        deviation = pstdev(history)
        score = 0.0 if deviation == 0 else abs(values[index] - mean(history)) / deviation
        if score >= threshold:
            detections.append(_detection(index, score, f"rolling z-score {score:.4g} >= {threshold:.4g}"))
    return detections


def ewma(values: list[float], *, alpha: float = 0.2, threshold: float = 3.0) -> list[Detection]:
    if not 0 < alpha <= 1:
        raise ValueError("alpha must be in (0, 1]")
    if not values:
        return []
    level = values[0]
    detections: list[Detection] = []
    for index, value in enumerate(values[1:], start=1):
        residual = abs(value - level)
        level = alpha * value + (1 - alpha) * level
        if residual >= threshold:
            detections.append(_detection(index, residual, f"EWMA residual {residual:.4g} >= {threshold:.4g}"))
    return detections


def seasonal_baseline(
    values: list[float],
    *,
    period: int,
    threshold: float,
) -> list[Detection]:
    if period < 1:
        raise ValueError("period must be positive")
    detections: list[Detection] = []
    for index in range(period, len(values)):
        expected = values[index - period]
        deviation = abs(values[index] - expected)
        if deviation >= threshold:
            detections.append(_detection(index, deviation, f"seasonal deviation {deviation:.4g} >= {threshold:.4g}"))
    return detections


def change_point(values: list[float], *, window: int = 10, threshold: float = 3.0) -> list[Detection]:
    if window < 2:
        raise ValueError("window must be at least 2")
    detections: list[Detection] = []
    for index in range(window * 2, len(values)):
        before = mean(values[index - window * 2:index - window])
        after = mean(values[index - window:index])
        deviation = abs(after - before)
        spread = pstdev(values[index - window * 2:index]) or 1.0
        score = deviation / spread
        if score >= threshold:
            detections.append(_detection(index, score, f"change-point score {score:.4g} >= {threshold:.4g}"))
    return detections


def evaluate(
    detections: Iterable[Detection],
    labels: list[bool],
    *,
    sample_interval_seconds: float,
) -> BaselineMetrics:
    if sample_interval_seconds <= 0:
        raise ValueError("sample interval must be positive")
    predicted = {detection.index for detection in detections}
    actual = {index for index, label in enumerate(labels) if label}
    true_positive = len(predicted & actual)
    false_positive = len(predicted - actual)
    false_negative = len(actual - predicted)
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(actual) if actual else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    hours = len(labels) * sample_interval_seconds / 3600
    delays = [index - min((candidate for candidate in predicted if candidate <= index), default=index) for index in actual if predicted]
    return BaselineMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        false_alarms_per_hour=false_positive / hours if hours else 0.0,
        mean_detection_delay=sum(delays) / len(delays) * sample_interval_seconds if delays else None,
    )
