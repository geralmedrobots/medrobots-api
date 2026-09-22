from sqlalchemy.exc import OperationalError

from app.db.session import get_db


def test_wrong_methods(client, payload) -> None:
    assert client.get("/api/v1/contacts").status_code == 405
    assert client.post("/api/v1/health", json=payload).status_code == 405


def test_oversized_body_is_rejected(client) -> None:
    response = client.post("/api/v1/contacts", json={"message": "x" * 20_000})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"


def test_database_error_has_no_internal_details(client, payload) -> None:
    def broken_db():
        raise OperationalError("SELECT private", {}, Exception("secret password"))
        yield

    client.app.dependency_overrides[get_db] = broken_db
    response = client.post("/api/v1/contacts", json=payload)
    assert response.status_code == 503
    assert "private" not in response.text and "password" not in response.text
    client.app.dependency_overrides.clear()


def test_unexpected_error_has_no_stack_trace(client, payload) -> None:
    def broken_db():
        raise RuntimeError("secret token")
        yield

    client.app.dependency_overrides[get_db] = broken_db
    response = client.post("/api/v1/contacts", json=payload)
    assert response.status_code == 500
    assert "secret" not in response.text and "Traceback" not in response.text
    client.app.dependency_overrides.clear()


def test_cors_allows_only_configured_origins(client) -> None:
    headers = {"Access-Control-Request-Method": "POST"}
    allowed = client.options(
        "/api/v1/contacts", headers={**headers, "Origin": "https://medrobots.pt"}
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://medrobots.pt"

    denied = client.options(
        "/api/v1/contacts", headers={**headers, "Origin": "https://evil.example"}
    )
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers
