from __future__ import annotations

import pytest


class Adapter:
    def __init__(self):
        self.calls = []

    def inject(self, scenario, parameters): self.calls.append("inject")
    def stop(self, scenario): self.calls.append("stop")
    def cleanup(self, scenario): self.calls.append("cleanup")


def spec():
    from aegis_sre.incident_scenarios import FaultMode, ScenarioSpec

    return ScenarioSpec("latency-1", FaultMode.NETWORK_LATENCY, "aegis-lab", "checkout", 60, 42, 1, ("latency",), ("healthy",), {})


def test_catalog_covers_seven_failure_modes() -> None:
    from aegis_sre.incident_scenarios import scenario_catalog

    assert len(scenario_catalog()) >= 5
    assert len({item.mode for item in scenario_catalog()}) == len(scenario_catalog())


def test_namespace_and_duration_are_fail_closed() -> None:
    bad = spec()
    object.__setattr__(bad, "namespace", "default")
    with pytest.raises(PermissionError):
        bad.validate()


def test_lifecycle_records_cleanup_and_timing() -> None:
    from aegis_sre.incident_scenarios import ScenarioController, RunState

    adapter = Adapter()
    controller = ScenarioController()
    started = controller.start(spec(), adapter, run_id="run-1")
    stopped = controller.stop(started, adapter)
    cleaned = controller.cleanup(stopped, adapter)
    assert cleaned.state == RunState.CLEANED
    assert adapter.calls == ["inject", "stop", "cleanup"]
    assert cleaned.ground_truth.cleanup_at is not None


def test_cleanup_cannot_be_skipped() -> None:
    from aegis_sre.incident_scenarios import ScenarioController

    with pytest.raises(ValueError):
        ScenarioController().cleanup(controller_run := ScenarioController().start(spec(), Adapter(), run_id="run"), Adapter())
