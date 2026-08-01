"""Installed control-plane entry-point tests."""

from typing import Any

from pytest import MonkeyPatch

from aegis_sre import __main__
from aegis_sre.settings import Settings


def test_run_uses_validated_network_settings(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def capture_run(application: str, **options: Any) -> None:
        captured["application"] = application
        captured.update(options)

    monkeypatch.setattr(
        __main__, "get_settings", lambda: Settings(api_host="127.0.0.1", api_port=9090)
    )
    monkeypatch.setattr(__main__.uvicorn, "run", capture_run)

    __main__.run()

    assert captured == {
        "application": "aegis_sre.api.app:create_app",
        "factory": True,
        "host": "127.0.0.1",
        "port": 9090,
        "log_config": None,
    }
