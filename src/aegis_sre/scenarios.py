"""Fail-closed incident scenario registry and experiment identity."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ScenarioOperation = Literal[
    "cpu_stress",
    "memory_pressure",
    "network_latency",
    "network_loss",
    "pod_restart",
    "config_toggle",
    "dependency_timeout",
]


class VersionSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    workload: str = Field(min_length=1, max_length=128)
    chart: str = Field(min_length=1, max_length=128)
    commit: str = Field(min_length=1, max_length=128)
    dataset: str = Field(min_length=1, max_length=128)


class RemediationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: str = Field(min_length=1, max_length=128)
    rollback_operation: str = Field(min_length=1, max_length=128)
    approval_required: bool = True
    max_attempts: int = Field(default=1, ge=1, le=3)


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["scenario.v1"] = "scenario.v1"
    scenario_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1, max_length=256)
    target_service: str = Field(min_length=1, max_length=128)
    namespace: str = Field(min_length=1, max_length=128)
    operation: ScenarioOperation
    duration_seconds: int = Field(gt=0, le=600)
    seed: int = Field(ge=0, le=2**31 - 1)
    preconditions: tuple[str, ...] = Field(min_length=1)
    expected_signals: tuple[str, ...] = Field(min_length=1)
    ground_truth: tuple[str, ...] = Field(min_length=1)
    remediation: RemediationPlan
    cleanup: tuple[str, ...] = Field(min_length=1)
    versions: VersionSet

    @model_validator(mode="after")
    def require_safety_metadata(self) -> "Scenario":
        if not any("health" in item.lower() for item in self.preconditions):
            raise ValueError("a health precondition is required")
        if not any("capacity" in item.lower() for item in self.preconditions):
            raise ValueError("a capacity precondition is required")
        return self


class ExperimentRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_id: str
    scenario_id: str
    started_at: datetime
    scenario_fingerprint: str
    tool_version: str
    status: Literal["planned", "running", "succeeded", "failed", "aborted"] = "planned"


class SafetyEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed_namespaces: frozenset[str] = frozenset({"aegis-lab"})
    allowed_services: frozenset[str] = frozenset({"frontend", "checkout", "currency", "payment"})
    allowed_operations: frozenset[ScenarioOperation] = frozenset(
        {
            "cpu_stress",
            "memory_pressure",
            "network_latency",
            "network_loss",
            "pod_restart",
            "config_toggle",
            "dependency_timeout",
        }
    )
    max_duration_seconds: int = Field(default=300, gt=0, le=600)

    def validate_scenario(self, scenario: Scenario) -> None:
        violations: list[str] = []
        if scenario.namespace not in self.allowed_namespaces:
            violations.append("namespace is not allowlisted")
        if scenario.target_service not in self.allowed_services:
            violations.append("target service is not allowlisted")
        if scenario.operation not in self.allowed_operations:
            violations.append("operation is not allowlisted")
        if scenario.duration_seconds > self.max_duration_seconds:
            violations.append("duration exceeds safety envelope")
        if not scenario.remediation.approval_required:
            violations.append("remediation approval cannot be disabled")
        if violations:
            raise ValueError("; ".join(violations))


def scenario_fingerprint(scenario: Scenario) -> str:
    canonical = json.dumps(scenario.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def experiment_id(scenario: Scenario) -> str:
    """Return a reproducible identity for a scenario/version/seed combination."""
    return f"{scenario.scenario_id}-{scenario.seed}-{scenario_fingerprint(scenario)[:16]}"


def plan_run(scenario: Scenario, envelope: SafetyEnvelope, started_at: datetime, tool_version: str) -> ExperimentRun:
    envelope.validate_scenario(scenario)
    return ExperimentRun(
        experiment_id=experiment_id(scenario),
        scenario_id=scenario.scenario_id,
        started_at=started_at,
        scenario_fingerprint=scenario_fingerprint(scenario),
        tool_version=tool_version,
    )
