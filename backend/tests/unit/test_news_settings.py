"""Invalid scheduler/provider configuration fails before starting a worker."""

import pytest
from pydantic import SecretStr, ValidationError

from src.core.news_settings import NewsSettings


@pytest.mark.parametrize("changes", [
    {"schedule": ("08:00", "08:00", "20:00")},
    {"schedule": ("8:00", "14:00", "20:00")},
    {"timezone": "Missing/TimeZone"},
    {"heartbeat_seconds": 60, "lease_seconds": 120},
    {"http_retries": 0},
    {"llm_retries": 0},
    {"llm_api_url": "https://user:password@provider.example/api"},
    {"llm_api_url": "https://provider.example/api?key=secret"},
    {"llm_api_url": "http://provider.example/api"},
])
def test_invalid_worker_settings_fail_closed(changes):
    with pytest.raises(ValidationError):
        NewsSettings(_env_file=None, **changes)


def test_readiness_requires_all_provider_values_and_repr_excludes_credentials():
    config = NewsSettings(
        _env_file=None, llm_model="fixture-model", llm_api_key=SecretStr("fixture-secret"),
        llm_api_url="https://provider.example/api",
    )
    assert config.llm_configured
    assert "fixture-secret" not in repr(config)
    assert "provider.example" not in repr(config)
    assert not config.model_copy(update={"llm_model": ""}).llm_configured


def test_invalid_provider_url_does_not_expose_its_credentials_in_startup_errors():
    with pytest.raises(ValidationError) as error:
        NewsSettings(_env_file=None, llm_api_url="https://fixture-user:fixture-secret@provider.example/api")
    assert "fixture-user" not in str(error.value)
    assert "fixture-secret" not in str(error.value)
