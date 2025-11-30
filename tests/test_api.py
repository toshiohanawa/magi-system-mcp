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
    # trace_idが各結果のメタデータに含まれる
    for result in data["results"].values():
        assert "metadata" in result
        assert "trace_id" in result["metadata"]
    # verbose=falseなのでtimelineはNone/欠落
    assert data.get("timeline") is None


def test_health_endpoint_reports_commands():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in {"ok", "degraded"}
    assert "commands" in data
    assert "details" in data
    # commands presence; values may be False if CLI not installed
    for key in ("codex", "claude", "gemini"):
        assert key in data["commands"]
        assert isinstance(data["commands"][key], bool)
        assert key in data["details"]
        assert isinstance(data["details"][key], dict)
        assert "available" in data["details"][key]


def test_start_endpoint_respects_strict_policy():
    client = TestClient(app)
    response = client.post(
        "/magi/start",
        json={
            "initial_prompt": "demo",
            "fallback_policy": "strict",
            "verbose": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "logs" in data
    assert "summary" in data
    assert "timeline" in data
    assert isinstance(data["logs"], list)
    assert isinstance(data["summary"], str)
    assert isinstance(data["timeline"], list)
    results = data["results"]
    # strictの場合、最初の失敗で後続がskippedになる（環境ではCLI未起動のため想定通りエラー）
    assert results["codex"]["metadata"]["status"] in {"error", "ok"}  # 実環境次第でOKになり得る
    if results["codex"]["metadata"]["status"] == "error":
        assert results["claude"]["metadata"]["status"] == "skipped"
        assert results["gemini"]["metadata"]["status"] == "skipped"
        # timelineとlogsにもskip理由が含まれている
        assert any(entry.get("status") == "skipped" for entry in data["logs"])
        assert any("skipped" in line for line in data["timeline"])


def test_start_endpoint_verbose_false():
    """verbose=falseの場合、logsとsummaryがNoneになることを確認"""
    client = TestClient(app)
    response = client.post(
        "/magi/start",
        json={
            "initial_prompt": "demo",
            "verbose": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    # verbose=falseの場合、logsとsummaryはNoneまたは含まれない
    assert data.get("logs") is None or data.get("logs") == []
    assert data.get("summary") is None or data.get("summary") == ""
    assert data.get("timeline") is None or data.get("timeline") == []


def test_start_endpoint_verbose_true():
    """verbose=trueの場合、logsとsummaryが返されることを確認"""
    client = TestClient(app)
    response = client.post(
        "/magi/start",
        json={
            "initial_prompt": "demo",
            "verbose": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "logs" in data
    assert "summary" in data
    assert "timeline" in data
    assert isinstance(data["logs"], list)
    assert isinstance(data["summary"], str)
    assert isinstance(data["timeline"], list)
    # logsには各ステップの情報が含まれる
    if data["logs"]:
        for log_entry in data["logs"]:
            assert "t" in log_entry  # timestamp
            assert "step" in log_entry  # codex/claude/gemini
            assert "trace_id" in log_entry
            assert "status" in log_entry
            assert "duration_ms" in log_entry or log_entry.get("duration_ms") is None
            assert "source" in log_entry or log_entry.get("source") is None
            assert "prompt_preview" in log_entry
            assert "content_preview" in log_entry
            assert "reason" in log_entry  # may be None
    # timelineには人間可読な進行が含まれる
    if data["timeline"]:
        assert all(isinstance(line, str) for line in data["timeline"])
