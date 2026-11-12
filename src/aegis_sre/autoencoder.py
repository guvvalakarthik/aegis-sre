"""Reproducible multivariate autoencoder training primitives.

The torch dependency is imported lazily so the package remains usable for the control
plane without installing the research-time training stack.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class AutoencoderConfig:
    latent_dim: int = 16
    epochs: int = 50
    batch_size: int = 64
    learning_rate: float = 1e-3
    seed: int = 42
    mask_value: float = 0.0


@dataclass(frozen=True)
class AutoencoderArtifact:
    model: Any
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    feature_names: tuple[str, ...]
    dataset_version: str
    split_hash: str
    config: AutoencoderConfig
    threshold: float | None = None


def fit_scaler(windows: Any) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Fit feature statistics on training windows only."""
    import numpy as np

    values = np.asarray(windows, dtype=float)
    if values.ndim != 3:
        raise ValueError("windows must have shape [batch, time, features]")
    mean = values.mean(axis=(0, 1))
    scale = values.std(axis=(0, 1))
    scale = np.where(scale > 1e-12, scale, 1.0)
    return tuple(mean.tolist()), tuple(scale.tolist())


def transform_windows(
    windows: Any,
    *,
    mean: Sequence[float],
    scale: Sequence[float],
    mask: Any | None = None,
    mask_value: float = 0.0,
) -> Any:
    """Standardize windows and make missingness explicit through a mask."""
    import numpy as np

    values = np.asarray(windows, dtype=float)
    missing = ~np.isfinite(values) if mask is None else np.asarray(mask, dtype=bool)
    values = np.nan_to_num(values, nan=mask_value, posinf=mask_value, neginf=mask_value)
    transformed = (values - np.asarray(mean)) / np.asarray(scale)
    return np.where(missing, mask_value, transformed)


def reconstruction_errors(model: Any, windows: Any) -> Any:
    """Return one reconstruction error per window for prediction-time inputs."""
    import numpy as np

    reconstructed = model(windows)
    errors = (reconstructed - windows) ** 2
    return np.asarray(errors).mean(axis=tuple(range(1, np.asarray(errors).ndim)))


def select_threshold(errors: Any, *, quantile: float = 0.995) -> float:
    """Select a threshold from calibration errors, never from the held-out test split."""
    import numpy as np

    if not 0.0 < quantile < 1.0:
        raise ValueError("quantile must be between 0 and 1")
    values = np.asarray(errors, dtype=float)
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError("calibration errors must be finite and non-empty")
    return float(np.quantile(values, quantile))


def per_feature_contributions(model: Any, windows: Any) -> Any:
    """Return mean squared reconstruction contribution for each feature."""
    import numpy as np

    reconstructed = np.asarray(model(windows))
    values = np.asarray(windows)
    if reconstructed.shape != values.shape:
        raise ValueError("model output must have the same shape as its input")
    return np.mean((reconstructed - values) ** 2, axis=1)


def save_artifact(artifact: AutoencoderArtifact, path: str | Path) -> None:
    import joblib

    joblib.dump(
        {
            "model": artifact.model,
            "mean": artifact.mean,
            "scale": artifact.scale,
            "feature_names": artifact.feature_names,
            "dataset_version": artifact.dataset_version,
            "split_hash": artifact.split_hash,
            "config": artifact.config,
            "threshold": artifact.threshold,
        },
        path,
    )
