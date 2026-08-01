"""Runtime configuration validation tests."""

import pytest
from pydantic import ValidationError

from aegis_sre.settings import Settings, get_settings


def test_api_port_must_be_valid() -> None:
    with pytest.raises(ValidationError):
        Settings(api_port=0)


def test_unknown_environment_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="preview")  # type: ignore[arg-type]


def test_process_settings_are_cached() -> None:
    get_settings.cache_clear()

    assert get_settings() is get_settings()
