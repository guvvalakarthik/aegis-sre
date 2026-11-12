"""Time-aware, point-in-time-safe dataset splitting and split hashes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field


SplitName = Literal["train", "validation", "calibration", "test", "ood"]


class FeatureSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=128)
    available_at: Literal["event_time", "ingestion_time", "offline_only"]
    unit: str = Field(min_length=1, max_length=64)
    nullable: bool = False


class Example(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    example_id: str = Field(min_length=1, max_length=256)
    incident_id: str = Field(min_length=1, max_length=256)
    scenario_variant: str = Field(min_length=1, max_length=128)
    event_time: datetime
    label_time: datetime
    features: Mapping[str, float | None]

    def point_in_time_safe(self, feature_specs: Mapping[str, FeatureSpec]) -> bool:
        if self.label_time < self.event_time:
            return False
        return all(
            name in feature_specs and spec.available_at != "offline_only"
            for name in self.features
        )


@dataclass(frozen=True)
class SplitAssignment:
    example_id: str
    split: SplitName


@dataclass(frozen=True)
class SplitPlan:
    dataset_version: str
    seed: int
    assignments: tuple[SplitAssignment, ...]
    split_hash: str


def build_split_plan(
    examples: Iterable[Example],
    *,
    dataset_version: str,
    seed: int,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.10,
    calibration_ratio: float = 0.10,
    held_out_variants: frozenset[str] = frozenset(),
) -> SplitPlan:
    if seed < 0:
        raise ValueError("seed must be non-negative")
    if not 0 < train_ratio < 1 or not 0 <= validation_ratio < 1 or not 0 <= calibration_ratio < 1:
        raise ValueError("split ratios must be in [0, 1)")
    if train_ratio + validation_ratio + calibration_ratio >= 1:
        raise ValueError("ratios must leave a non-empty test split")

    ordered = sorted(examples, key=lambda row: (row.event_time, row.example_id))
    assignments: list[SplitAssignment] = []
    eligible = [row for row in ordered if row.scenario_variant not in held_out_variants]
    total = len(eligible)
    train_end = int(total * train_ratio)
    validation_end = train_end + int(total * validation_ratio)
    calibration_end = validation_end + int(total * calibration_ratio)

    for row in ordered:
        if row.scenario_variant in held_out_variants:
            split: SplitName = "ood"
        else:
            index = eligible.index(row)
            if index < train_end:
                split = "train"
            elif index < validation_end:
                split = "validation"
            elif index < calibration_end:
                split = "calibration"
            else:
                split = "test"
        assignments.append(SplitAssignment(row.example_id, split))

    canonical = [
        {"example_id": item.example_id, "split": item.split}
        for item in assignments
    ]
    payload = json.dumps(
        {"dataset_version": dataset_version, "seed": seed, "assignments": canonical},
        sort_keys=True,
        separators=(",", ":"),
    )
    return SplitPlan(
        dataset_version=dataset_version,
        seed=seed,
        assignments=tuple(assignments),
        split_hash=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    )
