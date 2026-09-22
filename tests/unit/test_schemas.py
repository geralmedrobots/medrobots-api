import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.contact import ContactCreate


def test_contact_trims_whitespace(payload: dict[str, str]) -> None:
    data = ContactCreate.model_validate(payload)
    assert data.first_name == "Ana"
    assert data.last_name == "Silva"
    assert data.message == "Gostaria de saber mais."


@pytest.mark.parametrize("field", ["first_name", "last_name", "message"])
def test_required_text_rejects_blank(payload: dict[str, str], field: str) -> None:
    payload[field] = " \n "
    with pytest.raises(ValidationError):
        ContactCreate.model_validate(payload)


def test_settings_reject_wildcard_cors() -> None:
    with pytest.raises(ValidationError):
        Settings(cors_origins="*")


def test_production_requires_postgres() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", database_url="sqlite:///:memory:")


def test_production_requires_explicit_database_and_https_cors(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(environment="production")
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(
            environment="production",
            database_url="postgresql+psycopg://user:pass@localhost/db",
        )
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(
            environment="production",
            database_url="postgresql+psycopg://user:pass@localhost/db",
            cors_origins="http://example.com",
        )
    with pytest.raises(ValidationError, match="development database credentials"):
        Settings(
            environment="production",
            database_url="postgresql+psycopg://medrobots:medrobots@localhost/db",
            cors_origins="https://example.com",
        )
