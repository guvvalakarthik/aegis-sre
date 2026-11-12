from __future__ import annotations

import pytest


def test_late_fusion_preserves_scores_and_degrades_on_missing_signal() -> None:
    from aegis_sre.fusion import late_fuse

    evidence = late_fuse(
        {"telemetry": 0.8, "logs": 0.4},
        {"telemetry": True, "logs": False},
        weights={"telemetry": 1.0, "logs": 1.0},
    )
    assert evidence.fused_score == pytest.approx(0.8)
    assert evidence.modality_scores == {"telemetry": 0.8, "logs": 0.4}
    assert evidence.degraded is True


def test_fusion_rejects_no_available_modalities() -> None:
    from aegis_sre.fusion import late_fuse

    with pytest.raises(ValueError, match="available"):
        late_fuse({"telemetry": 0.8}, {"telemetry": False})


def test_bootstrap_is_reproducible() -> None:
    from aegis_sre.fusion import bootstrap_delta_ci

    args = ([0.8, 0.7, 0.9], [0.6, 0.7, 0.8])
    assert bootstrap_delta_ci(*args, seed=7, samples=100) == bootstrap_delta_ci(
        *args, seed=7, samples=100
    )


def test_model_card_requires_real_metrics() -> None:
    from aegis_sre.fusion import ModelCard

    card = ModelCard(
        name="fusion",
        version="v1",
        intended_use="candidate ranking",
        limitations=("not autonomous",),
        training_data="dataset-v1",
        evaluation_data="heldout-v1",
        metrics={"macro_f1": 0.7},
        safety_controls=("preserve modality scores",),
        operational_cost={"latency_ms": 1.0},
        ablation_reference="report-1",
    )
    assert '"status": "candidate"' in card.to_json()
