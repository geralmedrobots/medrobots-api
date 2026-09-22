from sqlalchemy.exc import OperationalError

from app.db.session import get_db


def test_liveness_endpoint(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_ok_when_database_available(client) -> None:
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_readiness_returns_503_when_database_unavailable(client) -> None:
    def broken_db():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))
        yield

    client.app.dependency_overrides[get_db] = broken_db
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    client.app.dependency_overrides.clear()


def test_liveness_does_not_touch_database(client) -> None:
    def broken_db():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))
        yield

    client.app.dependency_overrides[get_db] = broken_db
    try:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
    finally:
        client.app.dependency_overrides.clear()
