"""Role-aware operator dashboard API routes."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from aegis_sre.dashboard import BackendUnavailable, DashboardStore, Principal


class IncidentSummary(BaseModel):
    incident_id: str
    status: str
    severity: str
    started_at: str
    affected_services: tuple[str, ...]


class IncidentDetail(IncidentSummary):
    evidence: tuple[dict[str, object], ...]
    trajectory: tuple[dict[str, object], ...]
    remediation: dict[str, object] | None
    audit: tuple[dict[str, object], ...]


class ActionRequest(BaseModel):
    action: str = Field(min_length=1, max_length=128)


def _principal(request: Request) -> Principal:
    authenticator = getattr(request.app.state, "dashboard_authenticator", None)
    if authenticator is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="authentication unavailable")
    authorization = request.headers.get("Authorization", "")
    try:
        principal = authenticator(authorization)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication failed") from exc
    if not isinstance(principal, Principal):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid principal")
    return principal


def _store(request: Request) -> DashboardStore:
    store = getattr(request.app.state, "dashboard_store", None)
    if store is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="dashboard backend unavailable")
    return store


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/incidents", response_model=tuple[IncidentSummary, ...])
async def list_incidents(
    request: Request, principal: Principal = Depends(_principal)
) -> tuple[IncidentSummary, ...]:
    try:
        return tuple(IncidentSummary.model_validate(item) for item in _store(request).list_incidents(principal))
    except BackendUnavailable as exc:
        raise HTTPException(status_code=503, detail="incident backend degraded") from exc


@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
async def get_incident(request: Request, incident_id: str, principal: Principal = Depends(_principal)) -> IncidentDetail:
    try:
        return IncidentDetail.model_validate(_store(request).get_incident(incident_id, principal))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="incident not found") from exc
    except BackendUnavailable as exc:
        raise HTTPException(status_code=503, detail="incident backend degraded") from exc


@router.post("/incidents/{incident_id}/approval", status_code=202)
async def request_approval(request: Request, incident_id: str, body: ActionRequest, principal: Principal = Depends(_principal)) -> dict[str, Literal["accepted"]]:
    try:
        _store(request).request_approval(incident_id, principal, body.action)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="approval role required") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="incident not found") from exc
    return {"status": "accepted"}


@router.post("/incidents/{incident_id}/remediation", status_code=202)
async def request_remediation(request: Request, incident_id: str, body: ActionRequest, principal: Principal = Depends(_principal)) -> dict[str, Literal["accepted"]]:
    try:
        _store(request).request_remediation(incident_id, principal, body.action)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="operator role required") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="incident not found") from exc
    return {"status": "accepted"}
