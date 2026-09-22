import sqlite3

import pytest


def test_health(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_contact_persists_and_response_excludes_personal_data(
    client, database_url, payload
) -> None:
    response = client.post("/api/v1/contacts", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "new"
    assert isinstance(body["id"], int)
    assert "created_at" in body
    assert "email" not in body and "message" not in body

    path = database_url.removeprefix("sqlite+pysqlite:///")
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT first_name, last_name, email, message, status FROM contacts WHERE id = ?",
            (body["id"],),
        ).fetchone()
    assert row == ("Ana", "Silva", "ana@example.com", "Gostaria de saber mais.", "new")


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"email": "invalid"}, "email"),
        ({"first_name": ""}, "first_name"),
        ({"message": "x" * 5001}, "message"),
        ({"first_name": 42}, "first_name"),
        ({"address": []}, "address"),
        ({"unknown": "value"}, "unknown"),
    ],
)
def test_invalid_contact_returns_422(client, payload, change, field) -> None:
    payload.update(change)
    response = client.post("/api/v1/contacts", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert any(item["field"].endswith(field) for item in response.json()["error"]["details"])


def test_missing_required_field(client, payload) -> None:
    del payload["last_name"]
    response = client.post("/api/v1/contacts", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "body.last_name"


def test_openapi_and_documentation(client) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 200
    schema = client.get("/openapi.json").json()
    assert "/api/v1/contacts" in schema["paths"]
    assert schema["paths"]["/api/v1/contacts"]["post"]["responses"]["201"]
