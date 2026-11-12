"""Typed, redacted dashboard data boundary."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

_SECRET = re.compile(r"(?i)(password|secret|token|api[_-]?key|authorization)\s*[:=]\s*[^\s,;]+")


class BackendUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: frozenset[str]


@dataclass(frozen=True)
class IncidentSnapshot:
    incident_id: str
    status: str
    severity: str
    started_at: str
    affected_services: tuple[str, ...]
    evidence: tuple[dict[str, Any], ...]
    trajectory: tuple[dict[str, Any], ...]
    remediation: dict[str, Any] | None
    audit: tuple[dict[str, Any], ...]


class DashboardStore(Protocol):
    def list_incidents(self, principal: Principal) -> tuple[IncidentSnapshot, ...]:
        ...

    def get_incident(self, incident_id: str, principal: Principal) -> IncidentSnapshot:
        ...

    def request_approval(self, incident_id: str, principal: Principal, action: str) -> None:
        ...

    def request_remediation(self, incident_id: str, principal: Principal, action: str) -> None:
        ...


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return _SECRET.sub(r"\1=<REDACTED>", value)
    if isinstance(value, dict):
        return {str(key): redact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


class InMemoryDashboardStore:
    def __init__(self, incidents: tuple[IncidentSnapshot, ...] = ()) -> None:
        self._incidents = {item.incident_id: item for item in incidents}
        self.requests: list[tuple[str, str, str, str]] = []

    def list_incidents(self, principal: Principal) -> tuple[IncidentSnapshot, ...]:
        return tuple(redact(item.__dict__) for item in self._incidents.values())  # type: ignore[return-value]

    def get_incident(self, incident_id: str, principal: Principal) -> IncidentSnapshot:
        if incident_id not in self._incidents:
            raise KeyError(incident_id)
        return redact(self._incidents[incident_id].__dict__)  # type: ignore[return-value]

    def request_approval(self, incident_id: str, principal: Principal, action: str) -> None:
        if "approver" not in principal.roles and "admin" not in principal.roles:
            raise PermissionError("approver role required")
        if incident_id not in self._incidents:
            raise KeyError(incident_id)
        self.requests.append(("approval", incident_id, principal.subject, action))

    def request_remediation(self, incident_id: str, principal: Principal, action: str) -> None:
        if not principal.roles.intersection({"operator", "approver", "admin"}):
            raise PermissionError("operator role required")
        if incident_id not in self._incidents:
            raise KeyError(incident_id)
        self.requests.append(("remediation", incident_id, principal.subject, action))
