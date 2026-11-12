"""Dataset contract checks with quarantine reasons and leakage detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field


Split = Literal["train", "validation", "test"]


class DatasetRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    row_id: str = Field(min_length=1, max_length=256)
    incident_id: str = Field(min_length=1, max_length=256)
    split: Split
    service: str = Field(min_length=1, max_length=128)
    observed_at: datetime
    window_start: datetime
    window_end: datetime
    label: str = Field(min_length=1, max_length=128)
    features: Mapping[str, float]
    units: Mapping[str, str] = {}

    def valid_window(self) -> bool:
        return self.window_start <= self.observed_at <= self.window_end


@dataclass(frozen=True)
class QualityIssue:
    row_id: str
    code: str
    detail: str


@dataclass(frozen=True)
class QualityReport:
    dataset_version: str
    accepted_rows: int
    quarantined_rows: int
    issues: tuple[QualityIssue, ...]

    @property
    def passed(self) -> bool:
        return not self.issues


def validate_rows(rows: list[DatasetRow], dataset_version: str) -> QualityReport:
    issues: list[QualityIssue] = []
    row_ids: set[str] = set()
    incident_splits: dict[str, set[Split]] = {}
    windows: dict[str, list[tuple[datetime, datetime, str, Split]]] = {}

    for row in rows:
        if row.row_id in row_ids:
            issues.append(QualityIssue(row.row_id, "duplicate_row", "row_id occurs more than once"))
        row_ids.add(row.row_id)
        if not row.valid_window():
            issues.append(QualityIssue(row.row_id, "invalid_window", "observed_at is outside the declared window"))
        if not row.features:
            issues.append(QualityIssue(row.row_id, "missing_features", "feature map is empty"))
        if any(value != value or value in (float("inf"), float("-inf")) for value in row.features.values()):
            issues.append(QualityIssue(row.row_id, "invalid_numeric", "feature contains NaN or infinity"))
        incident_splits.setdefault(row.incident_id, set()).add(row.split)
        windows.setdefault(row.incident_id, []).append(
            (row.window_start, row.window_end, row.row_id, row.split)
        )

    for incident_id, splits in incident_splits.items():
        if len(splits) > 1:
            for row in rows:
                if row.incident_id == incident_id:
                    issues.append(
                        QualityIssue(row.row_id, "incident_split_leakage", f"{incident_id} occurs in {sorted(splits)}")
                    )

    for incident_id, incident_windows in windows.items():
        for index, left in enumerate(incident_windows):
            for right in incident_windows[index + 1 :]:
                overlaps = left[0] < right[1] and right[0] < left[1]
                if overlaps and left[3] != right[3]:
                    issues.append(
                        QualityIssue(
                            left[2],
                            "overlapping_window_leakage",
                            f"window overlaps {right[2]} for incident {incident_id}",
                        )
                    )

    issue_rows = {issue.row_id for issue in issues}
    return QualityReport(
        dataset_version=dataset_version,
        accepted_rows=len(rows) - len(issue_rows),
        quarantined_rows=len(issue_rows),
        issues=tuple(issues),
    )
