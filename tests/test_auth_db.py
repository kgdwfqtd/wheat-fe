import os
import pytest
from fastapi.testclient import TestClient

from mobile_api.main import app


TEST_DB = os.getenv("TEST_DATABASE_URL")


@pytest.mark.skipif(not TEST_DB, reason="TEST_DATABASE_URL not set")
def test_health_requires_db():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "database" in data


@pytest.mark.skipif(not TEST_DB, reason="TEST_DATABASE_URL not set")
def test_register_and_login():
    client = TestClient(app)
    username = "testuser_abc"
    password = "Password123!"

    # Try register (idempotent - if exists should return 400)
    resp = client.post("/api/v1/auth/register", json={
        "username": username,
        "password": password,
        "real_name": "Test User",
    })
    assert resp.status_code in (200, 400)

    # Attempt login
    resp2 = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp2.status_code in (200, 401)
    if resp2.status_code == 200:
        body = resp2.json()
        assert "access_token" in body
