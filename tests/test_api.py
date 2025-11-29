from fastapi.testclient import TestClient

from api.server import app


def test_start_endpoint_returns_session_id():
    client = TestClient(app)
    response = client.post("/magi/start", json={"initial_prompt": "demo"})
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "results" in data
    assert isinstance(data["results"], dict)


def test_health_endpoint_reports_commands():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in {"ok", "degraded"}
    assert "commands" in data
    # commands presence; values may be False if CLI not installed
    for key in ("codex", "claude", "gemini"):
        assert key in data["commands"]
        assert isinstance(data["commands"][key], bool)
