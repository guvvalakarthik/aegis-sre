"""Fail-closed dataset and feature quality validation contracts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Sequence


@dataclass(frozen=True)
class QualityIssue:
    check: str
    severity: str
    message: str
    affected: tuple[str, ...] = ()


@dataclass(frozen=True)
class FeatureQuality:
    feature: str
    variance: float
    correlation_with_label: float
    mutual_information: float
    stability_delta: float
    missing_rate: float


@dataclass(frozen=True)
class QualityReport:
    row_count: int
    feature_quality: tuple[FeatureQuality, ...]
    issues: tuple[QualityIssue, ...]
    dataset_version: str

    @property
    def trainable(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def assert_trainable(self) -> None:
        if not self.trainable:
            details = "; ".join(issue.message for issue in self.issues if issue.severity == "error")
            raise ValueError(f"training blocked by data quality checks: {details}")


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _correlation(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    denominator = math.sqrt(sum((a - left_mean) ** 2 for a in left) * sum((b - right_mean) ** 2 for b in right))
    return numerator / denominator if denominator else 0.0


def _mutual_information(feature: Sequence[float], label: Sequence[float], bins: int = 5) -> float:
    if len(feature) != len(label) or not feature:
        return 0.0
    low, high = min(feature), max(feature)
    width = (high - low) / bins if high > low else 1.0
    feature_bins = [min(bins - 1, int((value - low) / width)) for value in feature]
    pairs = {(bucket, target) for bucket, target in zip(feature_bins, label)}
    total = len(feature)
    result = 0.0
    for bucket, target in pairs:
        joint = sum(a == bucket and b == target for a, b in zip(feature_bins, label)) / total
        marginal_a = sum(a == bucket for a in feature_bins) / total
        marginal_b = sum(b == target for b in label) / total
        result += joint * math.log(joint / (marginal_a * marginal_b))
    return result


def validate_dataset(
    rows: Sequence[Mapping[str, object]],
    *,
    required_fields: Sequence[str],
    feature_fields: Sequence[str],
    label_field: str,
    timestamp_field: str,
    group_field: str,
    dataset_version: str,
    max_age_seconds: float | None = None,
    now_timestamp: str | None = None,
    allowed_fields: Sequence[str] | None = None,
) -> QualityReport:
    issues: list[QualityIssue] = []
    if not rows:
        return QualityReport(0, (), (QualityIssue("completeness", "error", "dataset is empty"),), dataset_version)
    fields = set(rows[0])
    missing_fields = set(required_fields) - fields
    if missing_fields:
        issues.append(QualityIssue("schema", "error", "required fields are missing", tuple(sorted(missing_fields))))
    if allowed_fields is not None:
        unexpected = fields - set(allowed_fields)
        if unexpected:
            issues.append(QualityIssue("schema", "error", "unexpected fields are present", tuple(sorted(unexpected))))
    for index, row in enumerate(rows):
        missing = set(required_fields) - set(row)
        if missing:
            issues.append(QualityIssue("completeness", "error", f"row {index} is missing required fields", tuple(sorted(missing))))
        if timestamp_field in row and not str(row[timestamp_field]):
            issues.append(QualityIssue("freshness", "error", f"row {index} has an empty timestamp"))
    if max_age_seconds is not None and now_timestamp is not None:
        try:
            now = datetime.fromisoformat(now_timestamp.replace("Z", "+00:00")).astimezone(timezone.utc)
            for row in rows:
                observed = datetime.fromisoformat(str(row.get(timestamp_field, "")).replace("Z", "+00:00")).astimezone(timezone.utc)
                age = (now - observed).total_seconds()
                if age < 0:
                    issues.append(QualityIssue("freshness", "error", "future-dated rows detected"))
                elif age > max_age_seconds:
                    issues.append(QualityIssue("freshness", "error", "stale rows exceed freshness limit"))
        except (TypeError, ValueError):
            issues.append(QualityIssue("freshness", "error", "timestamps are not valid ISO-8601 values"))
    leakage = detect_leakage(rows, feature_fields=feature_fields, label_field=label_field, timestamp_field=timestamp_field, group_field=group_field)
    issues.extend(leakage)
    labels = [_number(row.get(label_field)) for row in rows]
    numeric_labels = [value for value in labels if value is not None]
    feature_quality: list[FeatureQuality] = []
    midpoint = len(rows) // 2
    for feature in feature_fields:
        values = [_number(row.get(feature)) for row in rows]
        numeric = [value for value in values if value is not None]
        missing_rate = (len(values) - len(numeric)) / len(values)
        if not numeric:
            issues.append(QualityIssue("feature", "error", f"feature {feature} has no finite values", (feature,)))
            continue
        variance = sum((value - sum(numeric) / len(numeric)) ** 2 for value in numeric) / len(numeric)
        paired = [(value, label) for value, label in zip(values, labels) if value is not None and label is not None]
        x, y = zip(*paired) if paired else ((), ())
        first = [value for value in values[:midpoint] if value is not None]
        second = [value for value in values[midpoint:] if value is not None]
        first_mean = sum(first) / len(first) if first else 0.0
        second_mean = sum(second) / len(second) if second else 0.0
        feature_quality.append(FeatureQuality(
            feature, variance, _correlation(x, y), _mutual_information(x, y),
            second_mean - first_mean, missing_rate,
        ))
    return QualityReport(len(rows), tuple(feature_quality), tuple(issues), dataset_version)


def detect_leakage(
    rows: Sequence[Mapping[str, object]],
    *,
    feature_fields: Sequence[str],
    label_field: str,
    timestamp_field: str,
    group_field: str,
) -> tuple[QualityIssue, ...]:
    issues: list[QualityIssue] = []
    target_names = {label_field.lower(), "label", "target", "outcome", "future", "recovery"}
    leaked_names = tuple(sorted(feature for feature in feature_fields if feature.lower() in target_names))
    if leaked_names:
        issues.append(QualityIssue("label_leakage", "error", "feature names expose target fields", leaked_names))
    for index, row in enumerate(rows):
        feature_time = row.get("feature_timestamp", row.get(timestamp_field))
        label_time = row.get("label_timestamp")
        if label_time is not None and feature_time is not None and str(feature_time) > str(label_time):
            issues.append(QualityIssue("temporal_leakage", "error", f"row {index} uses data after label time"))
    groups: dict[str, set[str]] = {}
    for row in rows:
        group = str(row.get(group_field, ""))
        split = str(row.get("split", ""))
        if group and split:
            groups.setdefault(group, set()).add(split)
    cross_split = tuple(sorted(group for group, splits in groups.items() if len(splits) > 1))
    if cross_split:
        issues.append(QualityIssue("group_leakage", "error", "groups cross dataset splits", cross_split))
    return tuple(issues)
