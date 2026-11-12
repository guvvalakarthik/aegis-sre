from __future__ import annotations

import pytest


def test_masking_is_deterministic_and_never_masks_padding() -> None:
    torch = pytest.importorskip("torch")
    from aegis_sre.transformer_logs import mask_tokens

    ids = torch.tensor([[0, 3, 4, 5]])
    mask = torch.tensor([[False, True, True, True]])
    first = mask_tokens(ids, mask, probability=0.5, seed=7)
    second = mask_tokens(ids, mask, probability=0.5, seed=7)
    assert torch.equal(first[0], second[0])
    assert first[0][0, 0].item() == 0
    assert (first[1][0, 0].item()) == -100


def test_transformer_outputs_logits_attention_and_scores() -> None:
    torch = pytest.importorskip("torch")
    from aegis_sre.transformer_logs import (
        LogTransformerConfig,
        attention_attribution,
        anomaly_scores,
        build_model,
    )

    config = LogTransformerConfig(vocabulary_size=20, max_length=6, embedding_dim=8)
    model = build_model(config)
    ids = torch.ones((2, 6), dtype=torch.long)
    mask = torch.ones((2, 6), dtype=torch.bool)
    assert model(ids, mask).shape == (2, 6, 20)
    assert attention_attribution(model, ids, mask).shape == (6, 6)
    assert anomaly_scores(model, ids, mask).shape == (2, 6)


def test_invalid_masking_is_rejected() -> None:
    from aegis_sre.transformer_logs import mask_tokens

    with pytest.raises(ValueError):
        mask_tokens([[1]], [[True]], probability=0.0, seed=1)
