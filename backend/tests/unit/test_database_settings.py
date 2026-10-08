"""Database URLs must preserve administrator-selected credentials exactly."""

import pytest
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from src.core.settings import DBSettings


@pytest.mark.parametrize(
    "password",
    ["test@fixture", "test%fixture", "test%2Ffixture", "test:/#?[]fixture", "test-пароль"],
    ids=["at-sign", "percent", "percent-like-escape", "url-delimiters", "unicode"],
)
def test_database_url_roundtrips_credentials_without_changing_connection_target(password):
    settings = DBSettings(
        _env_file=None,
        postgres_user="test@user",
        postgres_password=SecretStr(password),
        postgres_host="db",
        postgres_port=5432,
        postgres_db="bks_test",
    )
    parsed = make_url(settings.database_url)
    assert parsed.drivername == "postgresql+asyncpg"
    assert parsed.username == "test@user"
    assert parsed.password == password
    assert parsed.host == "db"
    assert parsed.port == 5432
    assert parsed.database == "bks_test"
