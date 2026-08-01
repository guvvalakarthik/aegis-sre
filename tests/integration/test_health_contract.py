"""Health API contract tests."""

import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient

pytestmark = pytest.mark.anyio


async def test_liveness_contract(client: AsyncClient) -> None:
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "aegis-control-plane",
        "version": "0.1.0",
    }
    assert response.headers["X-Request-ID"]


async def test_readiness_contract_after_startup(client: AsyncClient) -> None:
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


async def test_readiness_fails_closed_when_service_is_unavailable(
    app: FastAPI, client: AsyncClient
) -> None:
    app.state.ready = False

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


async def test_metrics_expose_request_observability(client: AsyncClient) -> None:
    await client.get("/health/live")

    response = await client.get("/metrics")

    assert response.status_code == 200
    assert "aegis_http_requests_total" in response.text
