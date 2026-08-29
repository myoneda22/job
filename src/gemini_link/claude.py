"""A minimal Anthropic Messages API client, used for the cross-check feature.

Kept deliberately small — the comparison only needs one turn of plain text —
and built on the same injectable :class:`~gemini_link.gemini.Transport` so the
tests cover it without network access.
"""

from __future__ import annotations

import json
from typing import Any

from .config import Settings, load_settings
from .errors import ApiError, EmptyResponseError
from .gemini import Transport

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class ClaudeClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str | None = None,
        settings: Settings | None = None,
        transport: Transport | None = None,
    ):
        self.settings = settings or load_settings()
        self._api_key = api_key or self.settings.require_anthropic_key()
        self.model = model or self.settings.anthropic_model
        self.timeout = self.settings.timeout
        self._transport = transport or Transport()

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float | None = None,
        model: str | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model or self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        if temperature is not None:
            payload["temperature"] = temperature

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": API_VERSION,
            "Content-Type": "application/json",
        }
        status, _, data = self._transport.request(
            API_URL,
            headers=headers,
            body=json.dumps(payload).encode("utf-8"),
            timeout=self.timeout,
        )
        if not 200 <= status < 300:
            message = ""
            body: dict[str, Any] = {}
            if isinstance(data, (bytes, bytearray)):
                try:
                    body = json.loads(data.decode("utf-8"))
                    message = body.get("error", {}).get("message", "")
                except ValueError:
                    message = data.decode("utf-8", "replace")[:500]
            raise ApiError(status, message or "request failed", body)

        parsed = json.loads(data.decode("utf-8"))
        text = "".join(
            block.get("text", "")
            for block in parsed.get("content", [])
            if block.get("type") == "text"
        )
        if not text:
            raise EmptyResponseError(
                f"Claude returned no text (stop_reason={parsed.get('stop_reason')})",
                finish_reason=parsed.get("stop_reason"),
                usage=parsed.get("usage", {}),
            )
        return text
