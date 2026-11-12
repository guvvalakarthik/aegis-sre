from __future__ import annotations

import pytest


def test_patchify_never_adds_future_values() -> None:
    torch = pytest.importorskip("torch")
    from aegis_sre.patchtst import patchify

    context = torch.arange(8.0).reshape(1, 1, 8)
    patches = patchify(context, patch_length=4, stride=2)
    assert patches.shape == (1, 1, 3, 4)
    assert patches[0, 0, -1].tolist() == [4.0, 5.0, 6.0, 7.0]


def test_threshold_rejects_invalid_scores() -> None:
    torch = pytest.importorskip("torch")
    from aegis_sre.patchtst import calibrate_threshold

    with pytest.raises(ValueError):
        calibrate_threshold(torch.tensor([float("nan")]))


def test_forecast_shape_and_residuals() -> None:
    torch = pytest.importorskip("torch")
    from aegis_sre.patchtst import (
        PatchTSTConfig,
        absolute_residual_scores,
        build_patchtst,
    )

    config = PatchTSTConfig(channels=2, context_length=8, horizon=3, patch_length=4)
    model = build_patchtst(config)
    context = torch.randn(2, 2, 8)
    forecast = model(context)
    assert forecast.shape == (2, 2, 3)
    assert absolute_residual_scores(forecast, torch.zeros_like(forecast)).shape == (2, 2)
