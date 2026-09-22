from functools import cached_property
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_name: str = Field(default="Med Robots API", min_length=1)
    app_version: str = Field(default="0.1.0", min_length=1)
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://medrobots:medrobots@localhost:5432/medrobots"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("app_name", "app_version", "database_url", "cors_origins", mode="before")
    @classmethod
    def reject_blank(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must be a non-empty string")
        return value.strip()

    @model_validator(mode="after")
    def validate_urls(self) -> Settings:
        url = make_url(self.database_url)
        if url.drivername not in {"postgresql+psycopg", "sqlite", "sqlite+pysqlite"}:
            raise ValueError("DATABASE_URL must use PostgreSQL with psycopg or SQLite for tests")
        if self.environment == "production" and url.drivername != "postgresql+psycopg":
            raise ValueError("production requires PostgreSQL with psycopg")
        if not self.allowed_origins:
            raise ValueError("CORS_ORIGINS must include at least one origin")
        return self

    @cached_property
    def allowed_origins(self) -> tuple[str, ...]:
        from urllib.parse import urlsplit

        origins = tuple(origin.strip().rstrip("/") for origin in self.cors_origins.split(","))
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                origin == "*"
                or parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("CORS_ORIGINS must contain explicit HTTP(S) origins")
        return origins
