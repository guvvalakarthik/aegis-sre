"""Leakage-safe PatchTST-style forecasting and residual scoring primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PatchTSTConfig:
    channels: int
    context_length: int
    horizon: int
    patch_length: int = 16
    stride: int = 8
    d_model: int = 64
    heads: int = 4
    layers: int = 2
    dropout: float = 0.1
    seed: int = 42


@dataclass(frozen=True)
class ForecastBatch:
    context: Any
    target: Any

    def validate(self, config: PatchTSTConfig) -> None:
        if self.context.ndim != 3 or self.target.ndim != 3:
            raise ValueError("context and target must have shape [batch, channels, time]")
        if self.context.shape[1] != config.channels:
            raise ValueError("context channel count does not match config")
        if self.context.shape[2] != config.context_length:
            raise ValueError("context length does not match config")
        if self.target.shape[1:] != (config.channels, config.horizon):
            raise ValueError("target shape does not match config")


def patchify(context: Any, *, patch_length: int, stride: int) -> Any:
    """Create temporal patches without looking beyond the supplied context."""
    if context.ndim != 3:
        raise ValueError("context must have shape [batch, channels, time]")
    if patch_length < 1 or stride < 1:
        raise ValueError("patch_length and stride must be positive")
    if context.shape[-1] < patch_length:
        raise ValueError("context is shorter than patch_length")
    return context.unfold(-1, patch_length, stride)


def build_patchtst(config: PatchTSTConfig) -> Any:
    """Build a channel-independent PatchTST-style forecaster."""
    import torch
    from torch import nn

    if config.context_length < config.patch_length:
        raise ValueError("context_length must be >= patch_length")
    if config.d_model % config.heads:
        raise ValueError("d_model must be divisible by heads")
    if not 0.0 <= config.dropout < 1.0:
        raise ValueError("dropout must be in [0, 1)")

    class PatchTST(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            count = 1 + (config.context_length - config.patch_length) // config.stride
            self.patch = nn.Linear(config.patch_length, config.d_model)
            self.position = nn.Parameter(torch.zeros(1, count, config.d_model))
            layer = nn.TransformerEncoderLayer(
                d_model=config.d_model, nhead=config.heads,
                dropout=config.dropout, batch_first=True, norm_first=True,
            )
            self.encoder = nn.TransformerEncoder(layer, num_layers=config.layers)
            self.head = nn.Linear(count * config.d_model, config.horizon)

        def forward(self, context: Any) -> Any:
            if context.ndim != 3 or context.shape[1] != config.channels:
                raise ValueError("expected context [B,C,T]")
            patches = patchify(
                context, patch_length=config.patch_length, stride=config.stride
            )
            batch, channels, count, length = patches.shape
            encoded = self.patch(patches.reshape(batch * channels, count, length))
            encoded = self.encoder(encoded + self.position)
            forecast = self.head(encoded.flatten(start_dim=1))
            return forecast.reshape(batch, channels, config.horizon)

    torch.manual_seed(config.seed)
    return PatchTST()


def absolute_residual_scores(forecast: Any, observed: Any) -> Any:
    """Return channel-level residual scores for a forecast horizon."""
    if forecast.shape != observed.shape or forecast.ndim != 3:
        raise ValueError("forecast and observed must share shape [B,C,H]")
    return (forecast - observed).abs().mean(dim=-1)


def calibrate_threshold(scores: Any, *, quantile: float = 0.995) -> float:
    """Calibrate on a validation/calibration window, never on the test horizon."""
    if not 0.0 < quantile < 1.0:
        raise ValueError("quantile must be between 0 and 1")
    flattened = scores.detach().float().reshape(-1)
    if flattened.numel() == 0 or not bool(flattened.isfinite().all()):
        raise ValueError("calibration scores must be finite and non-empty")
    return float(flattened.quantile(quantile).item())


def gaussian_interval(forecast: Any, scale: Any, *, z: float = 1.96) -> tuple[Any, Any]:
    """Return a prediction interval from a positive scale estimate."""
    if z <= 0:
        raise ValueError("z must be positive")
    scale = scale.clamp_min(1e-6)
    return forecast - z * scale, forecast + z * scale
