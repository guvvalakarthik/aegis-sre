from __future__ import annotations

import pytest


def card():
    from aegis_sre.evaluation_datasets import DatasetCard

    return DatasetCard("incidents", "offline evaluation", ("telemetry-v1",), "verified cause", ("selection bias",), ("novel service",), ("small sample",))


def definition():
    from aegis_sre.evaluation_datasets import SplitDefinition, SplitStrategy

    return SplitDefinition(SplitStrategy.TEMPORAL, 42, 0.5, 0.25)


def rows():
    return [{"row_id": f"r{i}", "timestamp": f"2026-01-0{i+1}", "scenario": "s"} for i in range(4)]


def test_freeze_is_content_addressed_and_reproducible() -> None:
    from aegis_sre.evaluation_datasets import freeze_dataset, verify_reproduction

    dataset = freeze_dataset(rows(), dataset_version="v1", split_definition=definition(), provenance={"raw": "sha"}, card=card(), pipeline_version="p1")
    assert dataset.dataset_hash == dataset.content_hash()
    assert verify_reproduction(dataset, rows())


def test_dataset_card_requires_weakness_disclosures() -> None:
    from aegis_sre.evaluation_datasets import DatasetCard

    with pytest.raises(ValueError):
        DatasetCard("x", "use", ("s",), "label", (), (), ()).validate()


def test_splits_are_deterministic_and_disjoint() -> None:
    from aegis_sre.evaluation_datasets import freeze_dataset

    dataset = freeze_dataset(rows(), dataset_version="v1", split_definition=definition(), provenance={"raw": "sha"}, card=card(), pipeline_version="p1")
    values = list(dataset.splits.values())
    assert not (set(values[0]) & set(values[1]))
    assert not (set(values[0]) & set(values[2]))
