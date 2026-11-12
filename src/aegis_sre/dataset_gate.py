"""Versioned incident dataset manifest and integration-gate checks."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DatasetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_version: str = Field(pattern=r"^incident-v[0-9]+$")
    generated_at: datetime
    source_manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_versions: tuple[str, ...] = Field(min_length=1)
    split_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    scenario_versions: tuple[str, ...] = Field(min_length=25)
    root_cause_labels: tuple[str, ...] = Field(min_length=25)
    provenance_hashes: tuple[str, ...] = Field(min_length=1)
    quality_report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    contaminated_runs: int = Field(ge=0)
    excluded_runs: int = Field(ge=0)


class BenchmarkSubset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Literal["train", "validation", "calibration", "held-out", "ood"]
    split_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    scenario_labels: tuple[str, ...] = Field(min_length=1)
    protocol: str = Field(min_length=1, max_length=2_048)


def manifest_fingerprint(manifest: DatasetManifest) -> str:
    canonical = json.dumps(manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_gate(manifest: DatasetManifest, subsets: tuple[BenchmarkSubset, ...]) -> tuple[str, ...]:
    failures: list[str] = []
    if manifest.contaminated_runs:
        failures.append("contaminated runs must be zero")
    if not subsets:
        failures.append("at least one approved benchmark subset is required")
    if len({subset.split_hash for subset in subsets}) != len(subsets):
        failures.append("benchmark subsets must have distinct split hashes")
    if len(set(manifest.root_cause_labels)) < 25:
        failures.append("at least 25 root-cause labels are required")
    return tuple(failures)
