"""Deterministic point-in-time feature and dataset pipeline contracts."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


SCHEMA_VERSION = "features/v1"


@dataclass(frozen=True)
class FeatureRow:
    row_id: str
    scenario: str
    service: str
    run_id: str
    window_start: str
    window_end: str
    features: dict[str, float]
    missing: frozenset[str]
    lineage_hash: str


@dataclass(frozen=True)
class DatasetSplits:
    train: tuple[str, ...]
    validation: tuple[str, ...]
    test: tuple[str, ...]
    schema_version: str = SCHEMA_VERSION


def _finite(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def extract_features(
    records: Iterable[Mapping[str, object]],
    *,
    scenario: str,
    service: str,
    run_id: str,
    window_start: str,
    window_end: str,
    code_version: str,
) -> FeatureRow:
    """Aggregate only records timestamped inside the closed-open window."""
    if not all((scenario, service, run_id, window_start, window_end, code_version)):
        raise ValueError("feature identity and time window are required")
    if window_end <= window_start:
        raise ValueError("window_end must be after window_start")
    metrics: list[float] = []
    trace_latencies: list[float] = []
    log_count = 0
    error_logs = 0
    error_spans = 0
    accepted: list[dict[str, object]] = []
    for record in records:
        timestamp = str(record.get("timestamp", ""))
        if not window_start <= timestamp < window_end:
            continue
        accepted.append(dict(record))
        kind = str(record.get("kind", ""))
        value = _finite(record.get("value"))
        if kind == "metric" and value is not None:
            metrics.append(value)
        elif kind == "log":
            log_count += 1
            if str(record.get("level", "")).lower() in {"error", "fatal"}:
                error_logs += 1
        elif kind == "trace":
            if value is not None:
                trace_latencies.append(value)
            if bool(record.get("error")):
                error_spans += 1
    values = {
        "metric_mean": sum(metrics) / len(metrics) if metrics else 0.0,
        "metric_p95": _percentile(metrics, 0.95),
        "log_count": float(log_count),
        "log_error_rate": error_logs / log_count if log_count else 0.0,
        "trace_latency_p50": _percentile(trace_latencies, 0.50),
        "trace_latency_p95": _percentile(trace_latencies, 0.95),
        "trace_error_rate": error_spans / len(trace_latencies) if trace_latencies else 0.0,
    }
    missing = frozenset(name for name, value in values.items() if value == 0.0)
    lineage = hashlib.sha256(
        json.dumps(
            {"schema": SCHEMA_VERSION, "code": code_version, "records": accepted},
            sort_keys=True, default=str, separators=(",", ":"),
        ).encode()
    ).hexdigest()
    row_id = hashlib.sha256(f"{run_id}:{service}:{window_start}:{window_end}".encode()).hexdigest()
    return FeatureRow(row_id, scenario, service, run_id, window_start, window_end, values, missing, lineage)


@dataclass(frozen=True)
class FeatureNormalizer:
    means: dict[str, float]
    scales: dict[str, float]
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def fit(cls, rows: Sequence[FeatureRow]) -> "FeatureNormalizer":
        if not rows:
            raise ValueError("cannot fit normalizer on empty training rows")
        names = tuple(rows[0].features)
        means = {name: sum(row.features[name] for row in rows) / len(rows) for name in names}
        scales = {}
        for name in names:
            variance = sum((row.features[name] - means[name]) ** 2 for row in rows) / len(rows)
            scales[name] = math.sqrt(variance) or 1.0
        return cls(means, scales)

    def transform(self, row: FeatureRow) -> FeatureRow:
        if set(row.features) != set(self.means):
            raise ValueError("feature schema mismatch")
        values = {
            name: (value - self.means[name]) / self.scales[name]
            for name, value in row.features.items()
        }
        return FeatureRow(
            row.row_id, row.scenario, row.service, row.run_id, row.window_start,
            row.window_end, values, row.missing, row.lineage_hash,
        )


def make_splits(
    rows: Sequence[FeatureRow],
    *,
    seed: int = 42,
    train_fraction: float = 0.7,
    validation_fraction: float = 0.15,
) -> DatasetSplits:
    if not rows or not 0 < train_fraction < 1 or not 0 < validation_fraction < 1:
        raise ValueError("invalid split inputs")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("fractions must leave a test partition")
    groups: dict[tuple[str, str, str], list[FeatureRow]] = {}
    for row in rows:
        groups.setdefault((row.scenario, row.service, row.run_id), []).append(row)
    ordered = sorted(
        groups.items(),
        key=lambda pair: hashlib.sha256(f"{seed}:{pair[0]}".encode()).hexdigest(),
    )
    train: list[str] = []
    validation: list[str] = []
    test: list[str] = []
    total = len(ordered)
    for index, (_, members) in enumerate(ordered):
        fraction = (index + 0.5) / total
        target = train if fraction < train_fraction else validation if fraction < train_fraction + validation_fraction else test
        target.extend(member.row_id for member in members)
    if not train or not validation or not test:
        raise ValueError("dataset is too small for non-empty stratified splits")
    return DatasetSplits(tuple(train), tuple(validation), tuple(test))
