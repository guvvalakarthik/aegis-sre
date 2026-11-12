"""Comparable TCN/LSTM sequence-model contracts with safe masking and checkpoints."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


ModelKind = Literal["tcn", "lstm", "gru"]


@dataclass(frozen=True)
class SequenceConfig:
    kind: ModelKind
    input_dim: int
    hidden_dim: int = 64
    layers: int = 2
    kernel_size: int = 3
    classes: int = 2
    seed: int = 42


@dataclass(frozen=True)
class SequenceBatch:
    values: Any
    mask: Any
    labels: Any

    def validate(self) -> None:
        if self.values.ndim != 3:
            raise ValueError("values must have shape [batch, time, features]")
        if self.mask.shape != self.values.shape[:2]:
            raise ValueError("mask must have shape [batch, time]")
        if self.labels.shape[0] != self.values.shape[0]:
            raise ValueError("labels must have one entry per sequence")
        if self.mask.dtype is not bool and str(self.mask.dtype) != "torch.bool":
            raise ValueError("mask must be boolean; True means a real timestep")
        if not bool(self.mask.any(dim=1).all()):
            raise ValueError("every sequence must contain at least one real timestep")


@dataclass(frozen=True)
class CheckpointMetadata:
    schema_version: str
    model_config: SequenceConfig
    dataset_version: str
    split_hash: str
    preprocessing_version: str
    search_budget: str
    seed: int


def masked_mean(values: Any, mask: Any) -> Any:
    """Pool only real timesteps; padded values cannot affect predictions."""
    weights = mask.to(dtype=values.dtype).unsqueeze(-1)
    denominator = weights.sum(dim=1).clamp_min(1.0)
    return (values * weights).sum(dim=1) / denominator


def build_model(config: SequenceConfig) -> Any:
    """Build a TCN, LSTM, or GRU classifier with a common [B,T,F] interface."""
    import torch
    from torch import nn

    if config.input_dim < 1 or config.hidden_dim < 1 or config.layers < 1:
        raise ValueError("model dimensions must be positive")
    if config.kernel_size < 1 or config.kernel_size % 2 == 0:
        raise ValueError("kernel_size must be a positive odd number")

    class SequenceClassifier(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            if config.kind == "tcn":
                blocks: list[nn.Module] = []
                channels = config.input_dim
                for _ in range(config.layers):
                    blocks.extend([
                        nn.Conv1d(channels, config.hidden_dim, config.kernel_size,
                                  padding=config.kernel_size // 2),
                        nn.ReLU(),
                    ])
                    channels = config.hidden_dim
                self.encoder = nn.Sequential(*blocks)
                self.recurrent = None
            elif config.kind in ("lstm", "gru"):
                recurrent = nn.LSTM if config.kind == "lstm" else nn.GRU
                self.recurrent = recurrent(
                    config.input_dim, config.hidden_dim, config.layers,
                    batch_first=True, dropout=0.0,
                )
                self.encoder = None
            else:
                raise ValueError(f"unsupported model kind: {config.kind}")
            self.head = nn.Linear(config.hidden_dim, config.classes)

        def forward(self, values: Any, mask: Any) -> Any:
            if values.ndim != 3 or mask.shape != values.shape[:2]:
                raise ValueError("expected values [B,T,F] and mask [B,T]")
            if self.encoder is not None:
                encoded = self.encoder(values.transpose(1, 2)).transpose(1, 2)
            else:
                encoded, _ = self.recurrent(values)
            return self.head(masked_mean(encoded, mask))

    torch.manual_seed(config.seed)
    return SequenceClassifier()


def save_checkpoint(model: Any, path: str, metadata: CheckpointMetadata) -> None:
    import torch

    torch.save({
        "schema_version": metadata.schema_version,
        "metadata": asdict(metadata),
        "state_dict": model.state_dict(),
    }, path)


def load_checkpoint(path: str, *, map_location: str = "cpu") -> tuple[Any, CheckpointMetadata]:
    import torch

    payload = torch.load(path, map_location=map_location, weights_only=False)
    if payload.get("schema_version") != "sequence-model/v1":
        raise ValueError("unsupported or missing checkpoint schema")
    raw = payload["metadata"]
    config = SequenceConfig(**raw["model_config"])
    metadata = CheckpointMetadata(
        schema_version=payload["schema_version"],
        model_config=config,
        dataset_version=raw["dataset_version"],
        split_hash=raw["split_hash"],
        preprocessing_version=raw["preprocessing_version"],
        search_budget=raw["search_budget"],
        seed=raw["seed"],
    )
    model = build_model(config)
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model, metadata


def count_parameters(model: Any) -> int:
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
