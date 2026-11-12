"""Reproducible LSTM, autoencoder, and TCN telemetry model contracts."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Literal


ModelKind = Literal["lstm", "autoencoder", "tcn"]


@dataclass(frozen=True)
class DLConfig:
    kind: ModelKind
    input_dim: int
    hidden_dim: int = 64
    layers: int = 2
    kernel_size: int = 3
    learning_rate: float = 1e-3
    epochs: int = 50
    patience: int = 5
    seed: int = 42


@dataclass(frozen=True)
class TrainingMetadata:
    config: DLConfig
    dataset_version: str
    split_hash: str
    feature_schema_version: str
    model_version: str


@dataclass(frozen=True)
class TrainingHistory:
    train_loss: tuple[float, ...]
    validation_loss: tuple[float, ...]
    best_epoch: int

    def validate(self) -> None:
        if not self.train_loss or len(self.train_loss) != len(self.validation_loss):
            raise ValueError("training history is incomplete")
        if not all(math.isfinite(value) and value >= 0 for value in self.train_loss + self.validation_loss):
            raise ValueError("training losses must be finite and non-negative")


def seed_runtime(seed: int) -> None:
    import torch

    if seed < 0:
        raise ValueError("seed must be non-negative")
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)


def build_model(config: DLConfig) -> Any:
    import torch
    from torch import nn

    if config.input_dim < 1 or config.hidden_dim < 1 or config.layers < 1:
        raise ValueError("model dimensions must be positive")
    if config.kind == "tcn" and (config.kernel_size < 1 or config.kernel_size % 2 == 0):
        raise ValueError("TCN kernel size must be positive and odd")
    seed_runtime(config.seed)

    class TelemetryModel(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            if config.kind in ("lstm", "autoencoder"):
                self.encoder = nn.LSTM(
                    config.input_dim, config.hidden_dim, config.layers,
                    batch_first=True, dropout=0.0,
                )
                self.decoder = nn.Linear(config.hidden_dim, config.input_dim)
            elif config.kind == "tcn":
                layers: list[nn.Module] = []
                channels = config.input_dim
                for _ in range(config.layers):
                    layers.extend([
                        nn.Conv1d(channels, config.hidden_dim, config.kernel_size, padding=config.kernel_size // 2),
                        nn.ReLU(),
                    ])
                    channels = config.hidden_dim
                layers.append(nn.Conv1d(channels, config.input_dim, 1))
                self.encoder = nn.Sequential(*layers)
                self.decoder = None
            else:
                raise ValueError(f"unsupported model kind: {config.kind}")

        def forward(self, values: Any) -> Any:
            if values.ndim != 3 or values.shape[-1] != config.input_dim:
                raise ValueError("expected telemetry shape [batch, time, features]")
            if self.decoder is None:
                return self.encoder(values.transpose(1, 2)).transpose(1, 2)
            hidden, _ = self.encoder(values)
            return self.decoder(hidden)

    return TelemetryModel()


def train_reconstruction(
    model: Any,
    train_batches: Iterable[Any],
    validation_batches: Iterable[Any],
    *,
    config: DLConfig,
) -> TrainingHistory:
    import torch
    from torch import nn

    if config.epochs < 1 or config.patience < 1 or config.learning_rate <= 0:
        raise ValueError("invalid training configuration")
    seed_runtime(config.seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    loss_fn = nn.MSELoss()
    train_losses: list[float] = []
    validation_losses: list[float] = []
    best_state: dict[str, Any] | None = None
    best_loss = float("inf")
    best_epoch = 0
    stale = 0
    for epoch in range(config.epochs):
        model.train()
        train_values: list[float] = []
        for batch in train_batches:
            optimizer.zero_grad()
            loss = loss_fn(model(batch), batch)
            loss.backward()
            optimizer.step()
            train_values.append(float(loss.item()))
        if not train_values:
            raise ValueError("training batches cannot be empty")
        model.eval()
        with torch.no_grad():
            validation_values = [float(loss_fn(model(batch), batch).item()) for batch in validation_batches]
        if not validation_values:
            raise ValueError("validation batches cannot be empty")
        train_loss = sum(train_values) / len(train_values)
        validation_loss = sum(validation_values) / len(validation_values)
        train_losses.append(train_loss)
        validation_losses.append(validation_loss)
        if validation_loss < best_loss:
            best_loss = validation_loss
            best_epoch = epoch
            best_state = {key: value.detach().clone() for key, value in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
            if stale >= config.patience:
                break
    if best_state is None:
        raise RuntimeError("no checkpoint was produced")
    model.load_state_dict(best_state)
    history = TrainingHistory(tuple(train_losses), tuple(validation_losses), best_epoch)
    history.validate()
    return history


def reconstruction_errors(model: Any, batches: Iterable[Any]) -> list[float]:
    import torch

    model.eval()
    errors: list[float] = []
    with torch.no_grad():
        for batch in batches:
            values = (model(batch) - batch) ** 2
            errors.extend(values.mean(dim=tuple(range(1, values.ndim))).detach().cpu().tolist())
    if not errors or not all(math.isfinite(value) for value in errors):
        raise ValueError("reconstruction errors must be finite and non-empty")
    return errors


def calibrate_threshold(errors: Iterable[float], *, quantile: float = 0.995) -> float:
    values = sorted(float(error) for error in errors)
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("calibration errors must be finite and non-empty")
    if not 0.0 < quantile < 1.0:
        raise ValueError("quantile must be between 0 and 1")
    return values[min(len(values) - 1, int(quantile * len(values)))]


def save_checkpoint(model: Any, path: str, metadata: TrainingMetadata, history: TrainingHistory) -> None:
    import torch

    history.validate()
    torch.save({
        "schema_version": "dl-telemetry/v1",
        "metadata": asdict(metadata),
        "history": asdict(history),
        "state_dict": model.state_dict(),
    }, path)


def load_checkpoint(path: str, *, map_location: str = "cpu") -> tuple[Any, TrainingMetadata, TrainingHistory]:
    import torch

    payload = torch.load(path, map_location=map_location, weights_only=False)
    if payload.get("schema_version") != "dl-telemetry/v1":
        raise ValueError("unsupported checkpoint schema")
    raw = payload["metadata"]
    config = DLConfig(**raw["config"])
    metadata = TrainingMetadata(
        config, raw["dataset_version"], raw["split_hash"],
        raw["feature_schema_version"], raw["model_version"],
    )
    raw_history = payload["history"]
    history = TrainingHistory(tuple(raw_history["train_loss"]), tuple(raw_history["validation_loss"]), raw_history["best_epoch"])
    history.validate()
    model = build_model(config)
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model, metadata, history
