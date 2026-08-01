"""Command-line entry point for the AegisSRE control plane."""

import uvicorn

from aegis_sre.settings import get_settings


def run() -> None:
    """Run the HTTP control plane using the configured network binding."""
    settings = get_settings()
    uvicorn.run(
        "aegis_sre.api.app:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        log_config=None,
    )


if __name__ == "__main__":  # pragma: no cover - exercised through the installed entry point
    run()
