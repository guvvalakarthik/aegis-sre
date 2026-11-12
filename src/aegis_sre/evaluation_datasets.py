"""Immutable, content-addressed evaluation dataset contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping, Sequence


class SplitStrategy(StrEnum):
    TEMPORAL = "temporal"
    STRATIFIED = "stratified"
    LEAVE_ONE_SCENARIO_OUT = "leave_one_scenario_out"


@dataclass(frozen=True)
class SplitDefinition:
    strategy: SplitStrategy
    seed: int
    train_fraction: float
    validation_fraction: float
    held_out_scenario: str | None = None

    def validate(self) -> None:
        if self.seed < 0 or not 0 < self.train_fraction < 1 or not 0 < self.validation_fraction < 1:
            raise ValueError("invalid split definition")
        if self.train_fraction + self.validation_fraction >= 1:
            raise ValueError("split fractions must leave a test partition")
        if self.strategy == SplitStrategy.LEAVE_ONE_SCENARIO_OUT and not self.held_out_scenario:
            raise ValueError("leave-one-scenario-out requires a held-out scenario")


@dataclass(frozen=True)
class DatasetCard:
    name: str
    intended_use: str
    sources: tuple[str, ...]
    label_definition: str
    known_biases: tuple[str, ...]
    ood_scenarios: tuple[str, ...]
    limitations: tuple[str, ...]

    def validate(self) -> None:
        if not all((self.name, self.intended_use, self.sources, self.label_definition)):
            raise ValueError("dataset card identity and intended use are required")
        if not self.known_biases or not self.ood_scenarios or not self.limitations:
            raise ValueError("dataset card must disclose biases, OOD scenarios, and limitations")


@dataclass(frozen=True)
class FrozenDataset:
    dataset_hash: str
    dataset_version: str
    rows: tuple[Mapping[str, object], ...]
    split_definition: SplitDefinition
    splits: Mapping[str, tuple[str, ...]]
    provenance: Mapping[str, str]
    card: DatasetCard
    pipeline_version: str

    def validate(self) -> None:
        self.split_definition.validate()
        self.card.validate()
        if not self.dataset_hash or not self.dataset_version or not self.pipeline_version:
            raise ValueError("dataset identity and pipeline version are required")
        ids = [str(row.get("row_id", "")) for row in self.rows]
        if not ids or any(not row_id for row_id in ids) or len(set(ids)) != len(ids):
            raise ValueError("rows require unique row_id values")
        split_ids = {row_id for values in self.splits.values() for row_id in values}
        if split_ids != set(ids):
            raise ValueError("splits must cover every row exactly")
        if any(set(self.splits[a]) & set(self.splits[b]) for a in self.splits for b in self.splits if a < b):
            raise ValueError("splits must be disjoint")

    def content_hash(self) -> str:
        payload = {
            "version": self.dataset_version,
            "rows": [dict(sorted(row.items())) for row in self.rows],
            "split_definition": asdict(self.split_definition),
            "splits": {key: sorted(value) for key, value in sorted(self.splits.items())},
            "provenance": dict(sorted(self.provenance.items())),
            "pipeline_version": self.pipeline_version,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def freeze_dataset(
    rows: Sequence[Mapping[str, object]],
    *,
    dataset_version: str,
    split_definition: SplitDefinition,
    provenance: Mapping[str, str],
    card: DatasetCard,
    pipeline_version: str,
) -> FrozenDataset:
    split_definition.validate()
    card.validate()
    immutable_rows = tuple(MappingProxyType(dict(row)) for row in rows)
    if not immutable_rows:
        raise ValueError("cannot freeze an empty dataset")
    ids = [str(row.get("row_id", "")) for row in immutable_rows]
    if any(not row_id for row_id in ids) or len(set(ids)) != len(ids):
        raise ValueError("rows require unique row_id values")
    splits = make_splits(immutable_rows, split_definition)
    provisional = FrozenDataset(
        dataset_hash="", dataset_version=dataset_version, rows=immutable_rows,
        split_definition=split_definition, splits=splits, provenance=dict(provenance),
        card=card, pipeline_version=pipeline_version,
    )
    dataset_hash = provisional.content_hash()
    frozen = FrozenDataset(
        dataset_hash=dataset_hash,
        dataset_version=provisional.dataset_version,
        rows=provisional.rows,
        split_definition=provisional.split_definition,
        splits=provisional.splits,
        provenance=provisional.provenance,
        card=provisional.card,
        pipeline_version=provisional.pipeline_version,
    )
    frozen.validate()
    return frozen


def make_splits(rows: Sequence[Mapping[str, object]], definition: SplitDefinition) -> dict[str, tuple[str, ...]]:
    definition.validate()
    ordered = sorted(rows, key=lambda row: str(row.get("timestamp", row.get("row_id"))))
    if definition.strategy == SplitStrategy.LEAVE_ONE_SCENARIO_OUT:
        test = [str(row["row_id"]) for row in ordered if row.get("scenario") == definition.held_out_scenario]
        remaining = [row for row in ordered if str(row["row_id"]) not in test]
    elif definition.strategy == SplitStrategy.TEMPORAL:
        cutoff_train = int(len(ordered) * definition.train_fraction)
        cutoff_validation = int(len(ordered) * (definition.train_fraction + definition.validation_fraction))
        return {
            "train": tuple(str(row["row_id"]) for row in ordered[:cutoff_train]),
            "validation": tuple(str(row["row_id"]) for row in ordered[cutoff_train:cutoff_validation]),
            "test": tuple(str(row["row_id"]) for row in ordered[cutoff_validation:]),
        }
    else:
        remaining = ordered
        test = []
    ordered = sorted(remaining, key=lambda row: hashlib.sha256(f"{definition.seed}:{row['row_id']}".encode()).hexdigest())
    train_end = int(len(ordered) * definition.train_fraction)
    validation_end = int(len(ordered) * (definition.train_fraction + definition.validation_fraction))
    return {
        "train": tuple(str(row["row_id"]) for row in ordered[:train_end]),
        "validation": tuple(str(row["row_id"]) for row in ordered[train_end:validation_end]),
        "test": tuple(test or [str(row["row_id"]) for row in ordered[validation_end:]]),
    }


class DatasetStore:
    def __init__(self) -> None:
        self._datasets: dict[str, FrozenDataset] = {}

    def publish(self, dataset: FrozenDataset) -> str:
        dataset.validate()
        if dataset.dataset_hash != dataset.content_hash():
            raise ValueError("dataset hash does not match content")
        existing = self._datasets.get(dataset.dataset_hash)
        if existing is not None and existing != dataset:
            raise ValueError("content-addressed hash collision")
        self._datasets[dataset.dataset_hash] = dataset
        return dataset.dataset_hash

    def get(self, dataset_hash: str) -> FrozenDataset:
        if dataset_hash not in self._datasets:
            raise KeyError("dataset hash not found")
        return self._datasets[dataset_hash]


def verify_reproduction(dataset: FrozenDataset, reproduced_rows: Sequence[Mapping[str, object]]) -> bool:
    candidate = freeze_dataset(
        reproduced_rows, dataset_version=dataset.dataset_version,
        split_definition=dataset.split_definition, provenance=dataset.provenance,
        card=dataset.card, pipeline_version=dataset.pipeline_version,
    )
    return candidate.dataset_hash == dataset.dataset_hash
