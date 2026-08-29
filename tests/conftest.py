"""Shared fixtures.

Every test here runs offline: :class:`FakeTransport` stands in for the HTTP
layer, so the tests exercise real request building, retry, and parsing without
a network call or an API key.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gemini_link.config import Settings  # noqa: E402
from gemini_link.gemini import GeminiClient  # noqa: E402


class FakeTransport:
    """Replays queued responses and records what was sent."""

    def __init__(self, responses: list[tuple[int, dict[str, str], Any]] | None = None):
        self.responses = list(responses or [])
        self.requests: list[dict[str, Any]] = []
        self.gets: list[str] = []

    def queue_json(self, payload: dict[str, Any], status: int = 200, headers: dict | None = None):
        self.responses.append((status, headers or {}, json.dumps(payload).encode("utf-8")))
        return self

    def queue_error(self, status: int, message: str = "boom", headers: dict | None = None,
                    details: list | None = None):
        body = {"error": {"code": status, "message": message}}
        if details:
            body["error"]["details"] = details
        self.responses.append((status, headers or {}, json.dumps(body).encode("utf-8")))
        return self

    def queue_sse(self, chunks: list[str], status: int = 200):
        self.responses.append((status, {}, list(chunks)))
        return self

    def request(self, url, *, headers, body, timeout, stream=False):
        self.requests.append(
            {"url": url, "headers": headers, "body": json.loads(body), "stream": stream}
        )
        if not self.responses:
            raise AssertionError(f"no queued response for {url}")
        return self.responses.pop(0)

    def get(self, url, *, headers, timeout):
        self.gets.append(url)
        if not self.responses:
            raise AssertionError(f"no queued response for {url}")
        status, _headers, payload = self.responses.pop(0)
        return status, payload

    @property
    def last_body(self) -> dict[str, Any]:
        return self.requests[-1]["body"]


def text_response(text: str, **extra: Any) -> dict[str, Any]:
    """A minimal well-formed generateContent response."""
    payload: dict[str, Any] = {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}
        ],
        "modelVersion": "gemini-3.7-flash",
        "usageMetadata": {"totalTokenCount": 10},
    }
    payload.update(extra)
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gemini_api_key="test-gemini-key",
        gemini_model="gemini-3.7-flash",
        anthropic_api_key=None,
        anthropic_model="claude-sonnet-5",
        timeout=5.0,
        max_retries=3,
    )


@pytest.fixture
def transport() -> FakeTransport:
    return FakeTransport()


@pytest.fixture
def client(settings, transport) -> GeminiClient:
    # sleep is a no-op so retry tests do not actually wait.
    return GeminiClient(settings=settings, transport=transport, sleep=lambda _s: None)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Keep a developer's real keys out of the tests, and vice versa."""
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY",
                 "GEMINI_MODEL", "ANTHROPIC_MODEL", "GEMINI_TIMEOUT", "GEMINI_MAX_RETRIES"):
        monkeypatch.delenv(name, raising=False)


def function_call_response(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """A generateContent response whose only part is a function call."""
    return {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [{"functionCall": {"name": name, "args": args or {}}}],
                },
                "finishReason": "STOP",
            }
        ],
        "modelVersion": "gemini-3.7-flash",
    }
