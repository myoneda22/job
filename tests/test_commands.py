import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from claude_remote.main import app
from claude_remote.models import CommandResponse
from claude_remote.config import settings


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {settings.api_key}"}


def make_response(**kwargs) -> CommandResponse:
    defaults = dict(
        session_id="sess-1",
        response="Test response",
        cost_usd=0.001,
        turns=1,
        stop_reason="end_turn",
        is_error=False,
    )
    defaults.update(kwargs)
    return CommandResponse(**defaults)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_command_requires_auth(client):
    resp = client.post("/v1/commands", json={"prompt": "hello"})
    assert resp.status_code == 401


def test_command_rejects_wrong_token(client):
    resp = client.post(
        "/v1/commands",
        json={"prompt": "hello"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


def test_command_success(client, auth_headers):
    mock_response = make_response()
    with patch("claude_remote.routes.commands.run_command", return_value=mock_response):
        resp = client.post(
            "/v1/commands",
            json={"prompt": "Say hello"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "sess-1"
    assert data["response"] == "Test response"
    assert data["turns"] == 1
    assert data["is_error"] is False


def test_command_with_session_id(client, auth_headers):
    mock_response = make_response(session_id="existing-sess")
    with patch("claude_remote.routes.commands.run_command", return_value=mock_response) as mock_run:
        resp = client.post(
            "/v1/commands",
            json={"prompt": "Continue", "session_id": "existing-sess"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    call_req = mock_run.call_args[0][0]
    assert call_req.session_id == "existing-sess"


def test_command_validates_empty_prompt(client, auth_headers):
    resp = client.post(
        "/v1/commands",
        json={"prompt": ""},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_command_propagates_server_error(client, auth_headers):
    with patch(
        "claude_remote.routes.commands.run_command",
        side_effect=RuntimeError("SDK error"),
    ):
        resp = client.post(
            "/v1/commands",
            json={"prompt": "fail"},
            headers=auth_headers,
        )

    assert resp.status_code == 500
    assert "SDK error" in resp.json()["detail"]
