"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import RequestResponseEndpoint

from aegis_sre import __version__
from aegis_sre.api.routes.health import router as health_router
from aegis_sre.logging import configure_logging
from aegis_sre.settings import Settings, get_settings

LOGGER = structlog.get_logger(__name__)
REQUEST_COUNT = Counter(
    "aegis_http_requests_total",
    "Total HTTP requests handled by the control plane.",
    ("method", "route", "status"),
)
REQUEST_DURATION = Histogram(
    "aegis_http_request_duration_seconds",
    "Control-plane request duration in seconds.",
    ("method", "route"),
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured control-plane application."""
    runtime_settings = settings or get_settings()
    configure_logging(runtime_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.ready = True
        LOGGER.info(
            "service_started",
            service=runtime_settings.service_name,
            environment=runtime_settings.environment,
            version=__version__,
        )
        try:
            yield
        finally:
            app.state.ready = False
            LOGGER.info("service_stopped", service=runtime_settings.service_name)

    app = FastAPI(
        title="AegisSRE Control Plane",
        description="Control plane for evidence-grounded incident operations.",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.ready = False
    app.state.settings = runtime_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def observe_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        started_at = perf_counter()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        REQUEST_COUNT.labels(request.method, route_path, response.status_code).inc()
        REQUEST_DURATION.labels(request.method, route_path).observe(perf_counter() - started_at)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.include_router(health_router)
    return app
