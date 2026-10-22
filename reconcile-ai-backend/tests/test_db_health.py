from fastapi.testclient import TestClient

from app.main import app


def test_health_check_connects_to_database() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "connected"
