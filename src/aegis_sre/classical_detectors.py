"""Deterministic classical anomaly model adapters with validation-only calibration."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class ModelMetadata:
    model_kind: str
    model_version: str
    dataset_version: str
    split_hash: str
    feature_names: tuple[str, ...]
    seed: int


@dataclass(frozen=True)
class AnomalyModel:
    estimator: Any
    metadata: ModelMetadata

    def score(self, features: Any) -> Any:
        if self.metadata.model_kind == "pca":
            transformed = self.estimator.transform(features)
            reconstructed = self.estimator.inverse_transform(transformed)
            return ((features - reconstructed) ** 2).mean(axis=1)
        if self.metadata.model_kind == "arima":
            return self.estimator.resid
        if hasattr(self.estimator, "decision_function"):
            return -self.estimator.decision_function(features)
        raise ValueError("estimator does not support anomaly scoring")


@dataclass(frozen=True)
class CalibratedDetector:
    model: AnomalyModel
    threshold: float

    def predict(self, features: Any) -> tuple[Any, Any]:
        scores = self.model.score(features)
        return scores, scores >= self.threshold


def _validate_features(features: Any) -> None:
    if getattr(features, "ndim", 0) != 2 or features.shape[0] < 1:
        raise ValueError("features must be a non-empty [rows, columns] matrix")


def fit_isolation_forest(
    features: Any,
    *,
    feature_names: Sequence[str],
    dataset_version: str,
    split_hash: str,
    seed: int = 42,
    estimators: int = 200,
) -> AnomalyModel:
    from sklearn.ensemble import IsolationForest

    _validate_features(features)
    estimator = IsolationForest(n_estimators=estimators, random_state=seed, n_jobs=1)
    estimator.fit(features)
    return AnomalyModel(estimator, ModelMetadata("isolation_forest", f"iforest-{seed}-{estimators}", dataset_version, split_hash, tuple(feature_names), seed))


def fit_one_class_svm(
    features: Any,
    *,
    feature_names: Sequence[str],
    dataset_version: str,
    split_hash: str,
    seed: int = 42,
    nu: float = 0.05,
) -> AnomalyModel:
    from sklearn.svm import OneClassSVM

    _validate_features(features)
    if not 0.0 < nu <= 1.0:
        raise ValueError("nu must be in (0, 1]")
    estimator = OneClassSVM(nu=nu, kernel="rbf", gamma="scale")
    estimator.fit(features)
    return AnomalyModel(estimator, ModelMetadata("one_class_svm", f"ocsvm-{seed}-{nu}", dataset_version, split_hash, tuple(feature_names), seed))


def fit_pca(
    features: Any,
    *,
    feature_names: Sequence[str],
    dataset_version: str,
    split_hash: str,
    components: int | float = 0.95,
) -> AnomalyModel:
    from sklearn.decomposition import PCA

    _validate_features(features)
    estimator = PCA(n_components=components, svd_solver="full", random_state=0)
    estimator.fit(features)
    return AnomalyModel(estimator, ModelMetadata("pca", f"pca-{components}", dataset_version, split_hash, tuple(feature_names), 0))


def fit_arima(
    values: Sequence[float],
    *,
    dataset_version: str,
    split_hash: str,
    order: tuple[int, int, int] = (1, 0, 0),
) -> AnomalyModel:
    from statsmodels.tsa.arima.model import ARIMA

    if len(values) < 10 or any(not math.isfinite(float(value)) for value in values):
        raise ValueError("ARIMA requires at least ten finite observations")
    if any(part < 0 for part in order):
        raise ValueError("ARIMA order must be non-negative")
    estimator = ARIMA(values, order=order).fit()
    return AnomalyModel(estimator, ModelMetadata("arima", f"arima-{order}", dataset_version, split_hash, ("value",), 0))


def calibrate(model: AnomalyModel, validation_features: Any, *, quantile: float = 0.995) -> CalibratedDetector:
    scores = model.score(validation_features)
    values = sorted(float(value) for value in scores)
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("validation scores must be finite and non-empty")
    if not 0.0 < quantile < 1.0:
        raise ValueError("quantile must be between 0 and 1")
    return CalibratedDetector(model, values[min(len(values) - 1, int(quantile * len(values)))])


def select_candidate(candidates: Sequence[tuple[AnomalyModel, float]]) -> AnomalyModel:
    """Select from validation scores only; ties resolve by model kind."""
    if not candidates or any(not math.isfinite(score) for _, score in candidates):
        raise ValueError("finite validation candidates are required")
    return sorted(candidates, key=lambda item: (-item[1], item[0].metadata.model_kind))[0][0]


def measure_inference(detector: CalibratedDetector, features: Any) -> tuple[Any, float]:
    started = time.perf_counter()
    result = detector.predict(features)
    return result, (time.perf_counter() - started) * 1000
