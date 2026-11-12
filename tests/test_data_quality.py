from __future__ import annotations

import pytest


def base_rows():
    return [
        {"x": 1, "label": 0, "timestamp": "2026-01-01T00:00:00Z", "group": "a", "split": "train"},
        {"x": 2, "label": 1, "timestamp": "2026-01-01T00:01:00Z", "group": "b", "split": "train"},
        {"x": 3, "label": 1, "timestamp": "2026-01-01T00:02:00Z", "group": "c", "split": "test"},
    ]


def test_quality_report_blocks_temporal_and_target_leakage() -> None:
    from aegis_sre.data_quality import validate_dataset

    rows = base_rows()
    rows[0]["future_feature"] = 1
    rows[0]["feature_timestamp"] = "2026-01-02T00:00:00Z"
    rows[0]["label_timestamp"] = "2026-01-01T00:00:00Z"
    report = validate_dataset(
        rows, required_fields=("x", "label", "timestamp", "group", "split"),
        feature_fields=("x", "future",), label_field="label", timestamp_field="timestamp",
        group_field="group", dataset_version="v1",
    )
    assert report.trainable is False
    with pytest.raises(ValueError, match="blocked"):
        report.assert_trainable()


def test_feature_quality_is_finite_and_missing_is_reported() -> None:
    from aegis_sre.data_quality import validate_dataset

    rows = base_rows()
    rows[0]["x"] = "not-a-number"
    report = validate_dataset(
        rows, required_fields=("x", "label", "timestamp", "group", "split"),
        feature_fields=("x",), label_field="label", timestamp_field="timestamp",
        group_field="group", dataset_version="v1",
    )
    assert report.feature_quality[0].missing_rate > 0
