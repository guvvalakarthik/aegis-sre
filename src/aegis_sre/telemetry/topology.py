"""Time-aware service topology and deployment change correlation."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TopologyEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = Field(min_length=1, max_length=256)
    target: str = Field(min_length=1, max_length=256)
    relation: Literal["calls", "reads", "writes", "publishes", "consumes"]
    environment: str = Field(min_length=1, max_length=64)
    valid_from: datetime
    valid_to: datetime | None = None
    evidence_ids: tuple[str, ...] = ()
    inferred: bool = False
    confidence: float = Field(ge=0, le=1)

    def active_at(self, when: datetime) -> bool:
        return self.valid_from <= when and (self.valid_to is None or when < self.valid_to)


class ChangeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    change_id: str = Field(min_length=1, max_length=256)
    occurred_at: datetime
    service: str = Field(min_length=1, max_length=256)
    environment: str = Field(min_length=1, max_length=64)
    kind: Literal["deploy", "config", "feature_flag", "scale", "rollback"]
    revision: str = Field(min_length=1, max_length=256)
    source: str = Field(min_length=1, max_length=256)


def active_edges(edges: list[TopologyEdge], when: datetime, environment: str) -> list[TopologyEdge]:
    """Return only edges valid for the requested incident time and environment."""
    return [edge for edge in edges if edge.environment == environment and edge.active_at(when)]


def changes_in_window(
    changes: list[ChangeEvent],
    start: datetime,
    end: datetime,
    *,
    services: set[str] | None = None,
    environment: str | None = None,
) -> list[ChangeEvent]:
    """Find changes that overlap an incident window without changing source ordering."""
    result = [
        change
        for change in changes
        if start <= change.occurred_at <= end
        and (services is None or change.service in services)
        and (environment is None or change.environment == environment)
    ]
    return sorted(result, key=lambda change: (change.occurred_at, change.change_id))


def correlation_window(incident_at: datetime, before: timedelta, after: timedelta) -> tuple[datetime, datetime]:
    """Build a bounded query window around an incident timestamp."""
    if before < timedelta(0) or after < timedelta(0):
        raise ValueError("correlation windows cannot be negative")
    return incident_at - before, incident_at + after
