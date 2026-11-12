from __future__ import annotations


def test_zscore_is_deterministic_and_prefix_only() -> None:
    from aegis_sre.statistical_baselines import zscore_detector

    first = zscore_detector([0.0, 0.0, 4.0], baseline_mean=0.0, baseline_std=1.0)
    second = zscore_detector([0.0, 0.0, 4.0, 1000.0], baseline_mean=0.0, baseline_std=1.0)
    assert first == second[:3]
    assert first[-1].anomalous is True


def test_ewma_and_seasonal_expose_windows() -> None:
    from aegis_sre.statistical_baselines import ewma_detector, seasonal_detector

    assert ewma_detector([1, 1, 5], baseline_mean=1, baseline_std=1)[-1].window_end == 3
    assert seasonal_detector([1, 1, 1, 5], period=3, threshold=2)[-1].anomalous is True


def test_rule_and_slo_detectors() -> None:
    from aegis_sre.statistical_baselines import rule_detector, slo_detector

    detections = rule_detector([{"error": True}], [lambda record: 1.0 if record["error"] else 0.0])
    assert detections[0].anomalous is True
    assert slo_detector([1, 4], objective=3, direction="max")[-1].anomalous is True
