import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_auth.db")
os.environ.setdefault("AUTH_SECRET", "test-secret-that-is-long-enough-for-tests")

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


def registration_payload():
    return {
        "full_name": "  Asha   Sharma ",
        "email": "ASHA@example.com",
        "password": "strong-password-123",
        "mobile_number": "+91 98765 43210",
        "date_of_birth": "2004-03-12",
        "address": "12 Example Road",
        "city": "Pune",
        "state": "Maharashtra",
        "pin_code": "411001",
        "preferred_language": "hi",
    }


def auth_header(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_register_and_get_profile(client):
    response = client.post("/api/auth/register", json=registration_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["full_name"] == "Asha Sharma"
    assert body["user"]["email"] == "asha@example.com"
    assert body["user"]["city"] == "Pune"
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]

    profile = client.get("/api/auth/me", headers=auth_header(response))
    assert profile.status_code == 200
    assert profile.json()["preferred_language"] == "hi"


def test_duplicate_email_is_rejected_case_insensitively(client):
    assert client.post("/api/auth/register", json=registration_payload()).status_code == 201
    duplicate = registration_payload()
    duplicate["email"] = "asha@EXAMPLE.com"
    response = client.post("/api/auth/register", json=duplicate)
    assert response.status_code == 409


def test_login_and_wrong_password(client):
    client.post("/api/auth/register", json=registration_payload())
    response = client.post("/api/auth/login", json={"email": "ASHA@example.com", "password": "strong-password-123"})
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "asha@example.com"
    wrong = client.post("/api/auth/login", json={"email": "asha@example.com", "password": "wrong-password"})
    assert wrong.status_code == 401


def test_profile_update(client):
    registered = client.post("/api/auth/register", json=registration_payload())
    response = client.patch(
        "/api/auth/me",
        headers=auth_header(registered),
        json={"city": "Mumbai", "pin_code": "400001"},
    )
    assert response.status_code == 200
    assert response.json()["city"] == "Mumbai"
    assert response.json()["pin_code"] == "400001"
    assert response.json()["email"] == "asha@example.com"


def test_profile_requires_valid_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_registration_validation(client):
    payload = registration_payload()
    payload["email"] = "not-an-email"
    assert client.post("/api/auth/register", json=payload).status_code == 422

    payload = registration_payload()
    payload["password"] = "short"
    assert client.post("/api/auth/register", json=payload).status_code == 422
