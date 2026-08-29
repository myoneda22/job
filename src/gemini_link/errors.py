"""Exception types shared by the Gemini and Claude clients."""

from __future__ import annotations


class GeminiLinkError(Exception):
    """Base class for every error raised by this package."""


class ConfigError(GeminiLinkError):
    """A required setting (usually an API key) is missing or malformed."""


class ApiError(GeminiLinkError):
    """The upstream API returned a non-2xx response.

    ``status`` is the HTTP status code and ``payload`` the decoded error body
    when the server sent JSON, so callers can branch on the provider's own
    ``status`` string (e.g. ``RESOURCE_EXHAUSTED``) instead of parsing text.
    """

    def __init__(self, status: int, message: str, payload: dict | None = None):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message
        self.payload = payload or {}

    @property
    def retryable(self) -> bool:
        return self.status in (408, 429, 500, 502, 503, 504)


class RateLimitError(ApiError):
    """429 from the provider — quota or requests-per-minute exhausted."""


class EmptyResponseError(GeminiLinkError):
    """The call succeeded but produced no usable text.

    The common cause on thinking models is ``finishReason=MAX_TOKENS`` with the
    whole budget spent on reasoning tokens, which is why ``finish_reason`` and
    ``usage`` are carried here: the fix is a larger ``max_output_tokens`` or a
    lower thinking level, and the caller needs the numbers to tell which.
    """

    def __init__(self, message: str, finish_reason: str | None = None, usage: dict | None = None):
        super().__init__(message)
        self.finish_reason = finish_reason
        self.usage = usage or {}
