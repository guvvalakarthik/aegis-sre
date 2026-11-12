from __future__ import annotations

import pytest


def test_patch_shape_and_reconstruction_shape() -> None:
    torch = pytest.importorskip("torch")
    from aegis_sre.transformer_telemetry import TransformerTelemetryConfig, build_model, patchify

    config = TransformerTelemetryConfig(input_dim=3, context_length=12, patch_length=4, stride=2)
    values = torch.randn(2, 12, 3)
    assert patchify(values, patch_length=4, stride=2).shape == (2, 5, 4, 3)
    assert build_model(config)(values).shape == values.shape


def test_attention_attribution_is_inspectable() -> None:
    torch = pytest.importorskip("torch")
    from aegis_sre.transformer_telemetry import TransformerTelemetryConfig, attention_attribution, build_model

    config = TransformerTelemetryConfig(input_dim=2, context_length=8, patch_length=4, stride=2)
    values = torch.randn(1, 8, 2)
    attribution = attention_attribution(build_model(config), values)
    assert attribution.shape == (4, 4)
    assert torch.isfinite(attribution).all()


def test_checkpoint_reload_preserves_output(tmp_path) -> None:
    torch = pytest.importorskip("torch")
    from aegis_sre.transformer_telemetry import (
        TransformerMetadata, TransformerTelemetryConfig, build_model, load_checkpoint, save_checkpoint,
    )

    config = TransformerTelemetryConfig(input_dim=2, context_length=8)
    model = build_model(config).eval()
    metadata = TransformerMetadata(config, "dataset-v1", "split-v1", "features-v1", "transformer-v1")
    values = torch.randn(1, 8, 2)
    with torch.no_grad():
        expected = model(values)
    path = tmp_path / "model.pt"
    save_checkpoint(model, str(path), metadata)
    restored, restored_metadata = load_checkpoint(str(path))
    with torch.no_grad():
        actual = restored(values)
    assert torch.allclose(expected, actual)
    assert restored_metadata == metadata
