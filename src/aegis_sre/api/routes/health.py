"""Liveness and readiness endpoints."""

from typing import Literal

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from aegis_sre import __version__

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    """Stable health endpoint response contract."""

    status: Literal["healthy", "ready", "not_ready"]
    service: str
    version: str


@router.get("/live", response_model=HealthResponse)
async def liveness(request: Request) -> HealthResponse:
    """Report whether the HTTP process can serve requests."""
    return HealthResponse(
        status="healthy",
        service=request.app.state.settings.service_name,
        version=__version__,
    )


@router.get("/ready", response_model=HealthResponse)
async def readiness(request: Request) -> HealthResponse | JSONResponse:
    """Report whether startup completed and dependencies may receive traffic."""
    response = HealthResponse(
        status="ready" if request.app.state.ready else "not_ready",
        service=request.app.state.settings.service_name,
        version=__version__,
    )
    if request.app.state.ready:
        return response
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=response.model_dump()
    )
