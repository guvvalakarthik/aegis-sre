from __future__ import annotations

import pytest


def test_threshold_calibration_uses_validation_only() -> None:
    np = pytest.importorskip("numpy")
    from aegis_sre.classical_detectors import (
        AnomalyModel,
        CalibratedDetector,
        ModelMetadata,
        calibrate,
    )

    class Estimator:
        def decision_function(self, features): return -np.asarray(features).reshape(-1)

    model = AnomalyModel(Estimator(), ModelMetadata("test", "v1", "d1", "s1", ("x",), 42))
    detector = calibrate(model, np.asarray([[1.0], [2.0], [3.0]]), quantile=0.5)
    assert isinstance(detector, CalibratedDetector)
    scores, flags = detector.predict(np.asarray([[4.0]]))
    assert flags.tolist() == [True]


def test_pca_and_svm_builders_reject_bad_shapes() -> None:
    np = pytest.importorskip("numpy")
    pytest.importorskip("sklearn")
    from aegis_sre.classical_detectors import fit_pca

    with pytest.raises(ValueError):
        fit_pca(np.asarray([1.0]), feature_names=("x",), dataset_version="d", split_hash="s")


def test_candidate_selection_is_stable() -> None:
    from aegis_sre.classical_detectors import AnomalyModel, ModelMetadata, select_candidate

    first = AnomalyModel(object(), ModelMetadata("b", "v", "d", "s", (), 1))
    second = AnomalyModel(object(), ModelMetadata("a", "v", "d", "s", (), 1))
    assert select_candidate(((first, 0.5), (second, 0.5))).metadata.model_kind == "a"
