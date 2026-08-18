from fastapi.testclient import TestClient
from mobile_api.main import app


def test_root_redirect_or_docs():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code in (200, 307)


def test_get_config():
    client = TestClient(app)
    resp = client.get("/api/v1/config")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert "app_name" in data
