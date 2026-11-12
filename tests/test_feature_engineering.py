from __future__ import annotations

import math
import pytest


def records():
    return [
        {"timestamp": "2026-01-01T00:00:01Z", "kind": "metric", "value": 2},
        {"timestamp": "2026-01-01T00:00:02Z", "kind": "log", "level": "error"},
        {"timestamp": "2026-01-01T00:00:03Z", "kind": "trace", "value": 100, "error": False},
    ]


def test_features_are_point_in_time_and_reproducible() -> None:
    from aegis_sre.feature_engineering import extract_features

    first = extract_features(records(), scenario="latency", service="checkout", run_id="r1", window_start="2026-01-01T00:00:00Z", window_end="2026-01-01T00:00:04Z", code_version="v1")
    second = extract_features(records() + [{"timestamp": "2026-01-01T00:00:05Z", "kind": "metric", "value": 999}], scenario="latency", service="checkout", run_id="r1", window_start="2026-01-01T00:00:00Z", window_end="2026-01-01T00:00:04Z", code_version="v1")
    assert first == second


def test_missing_values_are_explicit_and_finite() -> None:
    from aegis_sre.feature_engineering import extract_features

    row = extract_features([], scenario="none", service="api", run_id="r", window_start="a", window_end="b", code_version="v1")
    assert row.missing
    assert all(math.isfinite(value) for value in row.features.values())


def test_normalizer_is_fit_and_applied_deterministically() -> None:
    from aegis_sre.feature_engineering import FeatureNormalizer, extract_features

    rows = [extract_features(records(), scenario=str(i), service="api", run_id=str(i), window_start="a", window_end="z", code_version="v1") for i in range(2)]
    normalizer = FeatureNormalizer.fit(rows)
    assert normalizer.transform(rows[0]) == normalizer.transform(rows[0])


def test_grouped_splits_are_reproducible() -> None:
    from aegis_sre.feature_engineering import extract_features, make_splits

    rows = [extract_features(records(), scenario=str(i), service="api", run_id=str(i), window_start="a", window_end="z", code_version="v1") for i in range(12)]
    assert make_splits(rows) == make_splits(rows)
