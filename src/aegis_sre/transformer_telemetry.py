"""Patch-based transformer telemetry reconstruction with attention attribution."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TransformerTelemetryConfig:
    input_dim: int
    context_length: int
    patch_length: int = 8
    stride: int = 4
    d_model: int = 64
    heads: int = 4
    layers: int = 2
    dropout: float = 0.1
    seed: int = 42


@dataclass(frozen=True)
class TransformerMetadata:
    config: TransformerTelemetryConfig
    dataset_version: str
    split_hash: str
    feature_schema_version: str
    model_version: str


def patchify(values: Any, *, patch_length: int, stride: int) -> Any:
    if values.ndim != 3 or patch_length < 1 or stride < 1:
        raise ValueError("invalid telemetry or patch configuration")
    if values.shape[1] < patch_length:
        raise ValueError("context is shorter than patch length")
    return values.unfold(1, patch_length, stride).permute(0, 1, 3, 2)


def build_model(config: TransformerTelemetryConfig) -> Any:
    import torch
    from torch import nn

    if config.input_dim < 1 or config.context_length < config.patch_length:
        raise ValueError("invalid input or context dimensions")
    if config.d_model % config.heads or config.layers < 1:
        raise ValueError("d_model must divide heads and layers must be positive")
    count = 1 + (config.context_length - config.patch_length) // config.stride
    torch.manual_seed(config.seed)

    class AttentionBlock(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.attention = nn.MultiheadAttention(
                config.d_model, config.heads, dropout=config.dropout, batch_first=True
            )
            self.norm = nn.LayerNorm(config.d_model)
            self.feed_forward = nn.Sequential(
                nn.Linear(config.d_model, config.d_model * 2),
                nn.GELU(),
                nn.Linear(config.d_model * 2, config.d_model),
            )

        def forward(self, values: Any) -> tuple[Any, Any]:
            attended, weights = self.attention(values, values, values, need_weights=True, average_attn_weights=False)
            hidden = self.norm(values + attended)
            return self.norm(hidden + self.feed_forward(hidden)), weights

    class TelemetryTransformer(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.patch = nn.Linear(config.patch_length * config.input_dim, config.d_model)
            self.position = nn.Parameter(torch.zeros(1, count, config.d_model))
            self.blocks = nn.ModuleList(AttentionBlock() for _ in range(config.layers))
            self.head = nn.Linear(config.d_model, config.patch_length * config.input_dim)

        def forward(self, values: Any, *, return_attention: bool = False) -> Any:
            if values.ndim != 3 or values.shape[1:] != (config.context_length, config.input_dim):
                raise ValueError("expected [batch, context, features] matching config")
            patches = patchify(values, patch_length=config.patch_length, stride=config.stride)
            batch, patch_count, patch_length, features = patches.shape
            hidden = self.patch(patches.reshape(batch, patch_count, patch_length * features)) + self.position
            attentions = []
            for block in self.blocks:
                hidden, weights = block(hidden)
                attentions.append(weights)
            outputs = self.head(hidden).reshape(batch, patch_count, patch_length, features)
            reconstruction = torch.zeros_like(values)
            counts = torch.zeros_like(values)
            for index in range(patch_count):
                start = index * config.stride
                reconstruction[:, start:start + config.patch_length] += outputs[:, index]
                counts[:, start:start + config.patch_length] += 1
            reconstruction = reconstruction / counts.clamp_min(1.0)
            return (reconstruction, torch.stack(attentions)) if return_attention else reconstruction

    return TelemetryTransformer()


def attention_attribution(model: Any, values: Any) -> Any:
    model.eval()
    _, attention = model(values, return_attention=True)
    return attention.detach().mean(dim=(0, 1, 2))


def reconstruction_errors(model: Any, values: Any) -> Any:
    import torch

    with torch.no_grad():
        reconstruction = model(values)
    errors = (reconstruction - values) ** 2
    return errors.mean(dim=(1, 2))


def save_checkpoint(model: Any, path: str, metadata: TransformerMetadata) -> None:
    import torch

    torch.save({
        "schema_version": "transformer-telemetry/v1",
        "metadata": asdict(metadata),
        "state_dict": model.state_dict(),
    }, path)


def load_checkpoint(path: str, *, map_location: str = "cpu") -> tuple[Any, TransformerMetadata]:
    import torch

    payload = torch.load(path, map_location=map_location, weights_only=False)
    if payload.get("schema_version") != "transformer-telemetry/v1":
        raise ValueError("unsupported checkpoint schema")
    raw = payload["metadata"]
    config = TransformerTelemetryConfig(**raw["config"])
    metadata = TransformerMetadata(
        config, raw["dataset_version"], raw["split_hash"],
        raw["feature_schema_version"], raw["model_version"],
    )
    model = build_model(config)
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model, metadata
