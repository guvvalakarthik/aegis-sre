"""Shared executable test fixtures."""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient

from aegis_sre.api.app import create_app
from aegis_sre.settings import Settings


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def app() -> FastAPI:
    return create_app(Settings(environment="test"))


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Run the real application lifespan around an HTTP test client."""
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as test_client:
            yield test_client
