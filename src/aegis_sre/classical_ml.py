"""Point-in-time-safe classical ML training and explanation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class ModelArtifact:
    model: Any
    feature_names: tuple[str, ...]
    dataset_version: str
    split_hash: str
    model_version: str
    calibration_version: str | None


def fit_isolation_forest(
    features: Any,
    *,
    feature_names: Sequence[str],
    dataset_version: str,
    split_hash: str,
    seed: int = 42,
    estimators: int = 200,
) -> ModelArtifact:
    """Fit only on the caller-provided training/calibration features."""
    from sklearn.ensemble import IsolationForest

    model = IsolationForest(
        n_estimators=estimators,
        random_state=seed,
        contamination="auto",
        n_jobs=1,
    )
    model.fit(features)
    return ModelArtifact(
        model=model,
        feature_names=tuple(feature_names),
        dataset_version=dataset_version,
        split_hash=split_hash,
        model_version=f"isolation-forest-{seed}-{estimators}",
        calibration_version=None,
    )


def fit_xgboost(
    features: Any,
    labels: Any,
    *,
    feature_names: Sequence[str],
    dataset_version: str,
    split_hash: str,
    seed: int = 42,
) -> ModelArtifact:
    """Fit a supervised classifier without touching the held-out test split."""
    from xgboost import XGBClassifier

    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=seed,
        n_jobs=1,
    )
    model.fit(features, labels)
    return ModelArtifact(
        model=model,
        feature_names=tuple(feature_names),
        dataset_version=dataset_version,
        split_hash=split_hash,
        model_version=f"xgboost-{seed}-300",
        calibration_version=None,
    )


def calibrate(
    artifact: ModelArtifact,
    calibration_features: Any,
    calibration_labels: Any,
    *,
    method: str = "sigmoid",
) -> ModelArtifact:
    """Calibrate on a calibration split and return a new immutable artifact."""
    from sklearn.calibration import CalibratedClassifierCV

    calibrated = CalibratedClassifierCV(artifact.model, method=method, cv="prefit")
    calibrated.fit(calibration_features, calibration_labels)
    return ModelArtifact(
        model=calibrated,
        feature_names=artifact.feature_names,
        dataset_version=artifact.dataset_version,
        split_hash=artifact.split_hash,
        model_version=artifact.model_version,
        calibration_version=f"{method}-calibration",
    )


def feature_importance(artifact: ModelArtifact) -> dict[str, float]:
    values = getattr(artifact.model, "feature_importances_", None)
    if values is None:
        return {}
    return dict(sorted(zip(artifact.feature_names, map(float, values)), key=lambda item: item[1], reverse=True))


def shap_importance(artifact: ModelArtifact, features: Any) -> dict[str, float]:
    """Return mean absolute SHAP values using prediction-time features only."""
    import shap

    explainer = shap.Explainer(artifact.model)
    values = explainer(features).values
    means = abs(values).mean(axis=0)
    return dict(sorted(zip(artifact.feature_names, map(float, means)), key=lambda item: item[1], reverse=True))


def save_artifact(artifact: ModelArtifact, path: str | Path) -> None:
    import joblib

    payload = {
        "model": artifact.model,
        "feature_names": artifact.feature_names,
        "dataset_version": artifact.dataset_version,
        "split_hash": artifact.split_hash,
        "model_version": artifact.model_version,
        "calibration_version": artifact.calibration_version,
    }
    joblib.dump(payload, path)
