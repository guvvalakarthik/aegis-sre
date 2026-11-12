from __future__ import annotations

import pytest


def spec():
    from aegis_sre.benchmark import BenchmarkSpec

    return BenchmarkSpec(
        benchmark_version="benchmark-v1",
        dataset_version="dataset-v1",
        split_hash="split-1",
        evaluation_version="eval-v1",
        incident_window="fixed",
        tasks=("anomaly",),
        latency_budget_ms=100.0,
        memory_budget_mb=512.0,
        cost_budget=1.0,
    )


def result(model: str, score: float, *, status: str = "passed"):
    from aegis_sre.benchmark import BenchmarkResult

    return BenchmarkResult(
        model=model,
        task="anomaly",
        status=status,
        artifact_url=f"https://example.test/{model}",
        dataset_version="dataset-v1",
        split_hash="split-1",
        metrics={"macro_f1": score} if status == "passed" else {},
        latency_ms=10.0,
        memory_mb=20.0,
        cost=0.1,
    )


def test_report_preserves_failed_and_inconclusive_results() -> None:
    from aegis_sre.benchmark import BenchmarkReport

    report = BenchmarkReport(spec(), (result("good", 0.8), result("failed", 0.0, status="failed")))
    report.validate()
    assert len(report.results) == 2


def test_selection_requires_two_independent_approvals() -> None:
    from aegis_sre.benchmark import BenchmarkReport, select_champions

    report = BenchmarkReport(spec(), (result("good", 0.8),))
    report = report.approve("Karthik", "review").approve("Trivedi", "reproduce")
    assert select_champions(report, metric="macro_f1", required_approvals=("Karthik", "Trivedi")) == {
        "anomaly": ("good", None)
    }


def test_mismatched_lineage_fails_closed() -> None:
    from aegis_sre.benchmark import BenchmarkReport

    bad = result("bad", 0.8)
    object.__setattr__(bad, "split_hash", "wrong")
    with pytest.raises(ValueError, match="lineage"):
        BenchmarkReport(spec(), (bad,)).validate()
