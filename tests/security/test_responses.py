from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.exc import OperationalError

from app.core.rate_limit import limiter
from app.db.session import get_db


def test_wrong_methods(client, payload) -> None:
    wrong_method = client.get("/api/v1/contacts")
    assert wrong_method.status_code == 405
    assert wrong_method.json()["error"]["code"] == "method_not_allowed"
    assert "POST" in wrong_method.headers["allow"]
    assert client.post("/api/v1/health", json=payload).status_code == 405


def test_unknown_route_and_trailing_slash(client) -> None:
    response = client.get("/api/v1/unknown")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Not found"}}
    assert client.get("/api/v1/health/", follow_redirects=False).status_code == 307


def test_missing_body_and_wrong_content_type(client) -> None:
    assert client.post("/api/v1/contacts").status_code == 422
    response = client.post(
        "/api/v1/contacts", content="plain text", headers={"Content-Type": "text/plain"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_oversized_body_is_rejected(client) -> None:
    response = client.post("/api/v1/contacts", json={"message": "x" * 20_000})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"


def test_streamed_body_without_content_length_is_limited(client) -> None:
    response = client.post(
        "/api/v1/contacts",
        content=iter([b"x" * 9000, b"y" * 9000]),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_security_headers_on_success_and_error(client) -> None:
    for path in ("/api/v1/health", "/api/v1/missing"):
        response = client.get(path)
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"


def test_contact_rate_limit_returns_429(client, payload) -> None:
    assert client.app.state.limiter is limiter
    assert any(middleware.cls is SlowAPIMiddleware for middleware in client.app.user_middleware)
    assert RateLimitExceeded in client.app.exception_handlers

    for _ in range(5):
        assert client.post("/api/v1/contacts", json=payload).status_code == 201

    response = client.post(
        "/api/v1/contacts", json=payload, headers={"X-Forwarded-For": "203.0.113.10"}
    )
    assert response.status_code == 429
    assert response.json() == {
        "error": {"code": "rate_limit_exceeded", "message": "Too many requests"}
    }
    for path in ("/api/v1/health", "/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 200


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
        raise RuntimeError("secret token at /private/app/config.env")
        yield

    client.app.dependency_overrides[get_db] = broken_db
    response = client.post("/api/v1/contacts", json=payload)
    assert response.status_code == 500
    assert all(value not in response.text for value in ("secret", "Traceback", "/private/"))
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
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

    actual = client.post(
        "/api/v1/contacts", json={"message": "abuse"}, headers={"Origin": "https://evil.example"}
    )
    assert actual.status_code == 403
    assert actual.json()["error"]["code"] == "origin_not_allowed"
    assert "access-control-allow-origin" not in actual.headers
