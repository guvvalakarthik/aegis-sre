from __future__ import annotations

import pytest


def test_all_architectures_share_reconstruction_shape() -> None:
    torch = pytest.importorskip("torch")
    from aegis_sre.dl_telemetry import DLConfig, build_model

    values = torch.randn(2, 5, 3)
    for kind in ("lstm", "autoencoder", "tcn"):
        model = build_model(DLConfig(kind=kind, input_dim=3, hidden_dim=4, kernel_size=3))
        assert model(values).shape == values.shape


def test_threshold_rejects_non_finite_calibration() -> None:
    from aegis_sre.dl_telemetry import calibrate_threshold

    with pytest.raises(ValueError):
        calibrate_threshold([0.1, float("nan")])


def test_checkpoint_reload_preserves_history_and_output(tmp_path) -> None:
    torch = pytest.importorskip("torch")
    from aegis_sre.dl_telemetry import (
        DLConfig,
        TrainingHistory,
        TrainingMetadata,
        build_model,
        load_checkpoint,
        save_checkpoint,
    )

    config = DLConfig("autoencoder", 2, hidden_dim=3)
    model = build_model(config).eval()
    history = TrainingHistory((1.0,), (0.8,), 0)
    metadata = TrainingMetadata(config, "dataset-v1", "split-v1", "features-v1", "ae-v1")
    values = torch.randn(1, 4, 2)
    with torch.no_grad():
        expected = model(values)
    path = tmp_path / "model.pt"
    save_checkpoint(model, str(path), metadata, history)
    restored, restored_metadata, restored_history = load_checkpoint(str(path))
    with torch.no_grad():
        actual = restored(values)
    assert torch.allclose(expected, actual)
    assert restored_metadata == metadata
    assert restored_history == history
