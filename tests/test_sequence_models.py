from __future__ import annotations

import pytest


def test_masked_mean_excludes_padding() -> None:
    torch = pytest.importorskip("torch")
    from aegis_sre.sequence_models import masked_mean

    values = torch.tensor([[[1.0], [3.0], [100.0]]])
    mask = torch.tensor([[True, True, False]])
    assert masked_mean(values, mask).item() == pytest.approx(2.0)


def test_model_rejects_all_padding() -> None:
    torch = pytest.importorskip("torch")
    from aegis_sre.sequence_models import SequenceBatch

    batch = SequenceBatch(
        values=torch.zeros((1, 2, 1)),
        mask=torch.zeros((1, 2), dtype=torch.bool),
        labels=torch.zeros(1, dtype=torch.long),
    )
    with pytest.raises(ValueError, match="at least one"):
        batch.validate()


def test_tcn_and_lstm_share_interface() -> None:
    torch = pytest.importorskip("torch")
    from aegis_sre.sequence_models import SequenceConfig, build_model

    values = torch.randn(2, 5, 3)
    mask = torch.tensor([[True, True, True, False, False], [True] * 5])
    for kind in ("tcn", "lstm"):
        model = build_model(SequenceConfig(kind=kind, input_dim=3, classes=4))
        assert model(values, mask).shape == (2, 4)
