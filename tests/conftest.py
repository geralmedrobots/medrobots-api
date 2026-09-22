import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.core.config import Settings
from app.db.base import Base
from app.db.models import Contact  # noqa: F401 - registers table metadata
from app.main import create_app


@pytest.fixture
def payload() -> dict[str, str]:
    return {
        "first_name": " Ana ",
        "last_name": " Silva ",
        "email": "ana@example.com",
        "phone": "+351 930 472 535",
        "address": "Coimbra",
        "message": " Gostaria de saber mais. ",
    }


@pytest.fixture
def database_url(tmp_path) -> str:
    url = f"sqlite+pysqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    return url


@pytest.fixture
def client(database_url: str):
    settings = Settings(
        environment="test",
        database_url=database_url,
        cors_origins="http://localhost:5173,https://medrobots.pt",
    )
    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
