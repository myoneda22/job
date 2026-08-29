"""A small, dependency-free client for the Gemini API (``v1beta``).

Built on ``urllib`` from the standard library rather than an SDK so the package
installs and its tests run with nothing but Python.  The transport is injectable
(:class:`Transport`), which is what lets the whole test suite exercise real
request/response handling without touching the network.

Covers what the rest of this repo needs: text generation, SSE streaming,
function calling, Google Search grounding, JSON-schema-constrained output,
thinking control, and retry with backoff.
"""

from __future__ import annotations

import contextlib
import json
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Sequence

from .config import Settings, load_settings
from .errors import ApiError, EmptyResponseError, RateLimitError, RetrievalError

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"

# Gemini 3.x takes generationConfig.thinkingConfig.thinkingLevel ("low"/"high");
# the 2.5 family takes an integer thinkingBudget instead.  Passing the wrong one
# is a 400, so the client picks by model family unless told explicitly.
_THINKING_LEVEL_FAMILIES = ("gemini-3",)


# Anything that is not exactly this counts as a failed fetch. Fail closed:
# an unrecognised status must never be mistaken for a successful retrieval.
URL_RETRIEVAL_SUCCESS = "URL_RETRIEVAL_STATUS_SUCCESS"


@dataclass
class RetrievedUrl:
    """One URL a ``url_context`` call tried to fetch, and how that went."""

    url: str
    status: str

    @property
    def ok(self) -> bool:
        return self.status == URL_RETRIEVAL_SUCCESS


@dataclass
class Source:
    """One grounded web source returned alongside a search-grounded answer."""

    title: str
    uri: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.title} <{self.uri}>"


@dataclass
class FunctionCall:
    name: str
    args: dict[str, Any]


@dataclass
class GeminiResponse:
    """A parsed ``generateContent`` response."""

    text: str
    model: str
    finish_reason: str | None = None
    function_calls: list[FunctionCall] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    retrieved_urls: list[RetrievedUrl] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def retrieval_failures(self) -> list[RetrievedUrl]:
        return [u for u in self.retrieved_urls if not u.ok]

    def require_retrieval(self) -> "GeminiResponse":
        """Raise unless every requested URL was actually fetched.

        Call this before believing a ``url_context`` answer. Observed
        behaviour: with a failed fetch the model still answers, from memory,
        with no hedging — so the retrieval status is the only reliable signal
        that the text is grounded in the page rather than in the weights.
        """
        failures = self.retrieval_failures
        if failures:
            raise RetrievalError(
                "the model answered without fetching "
                + ", ".join(f"{u.url} ({u.status})" for u in failures)
                + " — treat the answer as ungrounded and discard it",
                failures=[(u.url, u.status) for u in failures],
            )
        if not self.retrieved_urls:
            raise RetrievalError(
                "no URL retrieval was reported at all — the url_context tool "
                "was not used, so the answer is not grounded in any page"
            )
        return self

    def json(self) -> Any:
        """Decode ``text`` as JSON, tolerating a ```` ```json ```` fence."""
        body = self.text.strip()
        if body.startswith("```"):
            body = body.split("\n", 1)[1] if "\n" in body else body
            if body.endswith("```"):
                body = body[: -3]
            body = body.strip()
            if body.startswith("json"):
                body = body[4:].strip()
        return json.loads(body)


def _network_failure(exc: BaseException) -> tuple[int, dict[str, str], bytes]:
    """Render a transport-level failure as a retryable synthetic response."""
    reason = getattr(exc, "reason", None) or exc
    body = json.dumps(
        {"error": {"message": f"network error: {type(exc).__name__}: {reason}"}}
    ).encode("utf-8")
    return 504, {}, body


class Transport:
    """HTTP transport. Subclass/replace to test without network access."""

    def request(
        self,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes,
        timeout: float,
        stream: bool = False,
    ) -> tuple[int, dict[str, str], Any]:
        """Return ``(status, headers, payload)``.

        ``payload`` is decoded ``bytes`` for a normal call, or a line iterator
        when ``stream`` is set.
        """
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read()
            return exc.code, dict(exc.headers or {}), detail
        except (urllib.error.URLError, OSError) as exc:
            # A read timeout, reset, or DNS failure. Report it as a retryable
            # status so it flows through the same backoff loop as a 503 rather
            # than escaping as a raw socket traceback. url_context calls have
            # been measured at well over a minute, so this is a normal event.
            return _network_failure(exc)
        headers_out = dict(resp.headers or {})
        if stream:
            return resp.status, headers_out, resp
        with resp:
            return resp.status, headers_out, resp.read()

    def get(self, url: str, *, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()
        except (urllib.error.URLError, OSError) as exc:
            status, _headers, payload = _network_failure(exc)
            return status, payload


class GeminiClient:
    """Thin wrapper over the Gemini REST API.

    The API key is held only in memory and never appears in an exception
    message or a URL — it is passed in the ``x-goog-api-key`` header so it
    cannot leak through a logged request line.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str | None = None,
        settings: Settings | None = None,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.settings = settings or load_settings()
        self._api_key = api_key or self.settings.require_gemini_key()
        self.model = model or self.settings.gemini_model
        self.timeout = self.settings.timeout
        self.max_retries = self.settings.max_retries
        self._transport = transport or Transport()
        self._sleep = sleep

    # ---------------------------------------------------------------- helpers

    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}

    def _url(self, model: str, method: str, query: str = "") -> str:
        return f"{API_ROOT}/models/{model}:{method}{query}"

    def build_payload(
        self,
        prompt: str | None = None,
        *,
        contents: list[dict[str, Any]] | None = None,
        system: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        google_search: bool = False,
        url_context: bool = False,
        response_schema: dict[str, Any] | None = None,
        json_output: bool = False,
        thinking_level: str | None = None,
        thinking_budget: int | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Assemble a ``generateContent`` request body.

        Exposed (and tested) separately from the HTTP call so request shaping
        can be verified without a round trip.
        """
        if contents is None:
            if prompt is None:
                raise ValueError("pass either prompt or contents")
            contents = [{"role": "user", "parts": [{"text": prompt}]}]

        payload: dict[str, Any] = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        all_tools: list[dict[str, Any]] = list(tools or [])
        if google_search:
            all_tools.append({"google_search": {}})
        if url_context:
            all_tools.append({"url_context": {}})
        if all_tools:
            payload["tools"] = all_tools

        gen: dict[str, Any] = {}
        if temperature is not None:
            gen["temperature"] = temperature
        if max_output_tokens is not None:
            gen["maxOutputTokens"] = max_output_tokens
        if json_output or response_schema is not None:
            # Structured output and Google Search grounding are mutually
            # exclusive server-side; asking for both is a 400, so refuse here
            # with a message that says what to do instead.
            if google_search:
                raise ValueError(
                    "response_schema/json_output cannot be combined with google_search. "
                    "Ground first, then ask a second call to structure the result."
                )
            gen["responseMimeType"] = "application/json"
            if response_schema is not None:
                gen["responseSchema"] = response_schema

        thinking = self._thinking_config(
            model or self.model, thinking_level=thinking_level, thinking_budget=thinking_budget
        )
        if thinking:
            gen["thinkingConfig"] = thinking
        if gen:
            payload["generationConfig"] = gen
        return payload

    @staticmethod
    def _thinking_config(
        model: str, *, thinking_level: str | None, thinking_budget: int | None
    ) -> dict[str, Any]:
        if thinking_budget is not None:
            return {"thinkingBudget": thinking_budget}
        if thinking_level is None:
            return {}
        if model.startswith(_THINKING_LEVEL_FAMILIES):
            return {"thinkingLevel": thinking_level}
        # 2.5-era models only understand a numeric budget; map the level onto one.
        return {"thinkingBudget": {"low": 512, "medium": 4096, "high": 16384}.get(thinking_level, 0)}

    # ------------------------------------------------------------------ calls

    def _post(self, url: str, payload: dict[str, Any], *, stream: bool = False):
        """POST with retry on transient failures, honouring server retry hints."""
        body = json.dumps(payload).encode("utf-8")
        last_error: ApiError | None = None
        for attempt in range(self.max_retries + 1):
            status, headers, data = self._transport.request(
                url, headers=self._headers(), body=body, timeout=self.timeout, stream=stream
            )
            if 200 <= status < 300:
                return data
            error = self._to_error(status, data)
            last_error = error
            if not error.retryable or attempt == self.max_retries:
                raise error
            self._sleep(self._backoff(attempt, headers, error))
        raise last_error  # pragma: no cover - loop always raises or returns

    @staticmethod
    def _to_error(status: int, data: Any) -> ApiError:
        payload: dict[str, Any] = {}
        message = ""
        if isinstance(data, (bytes, bytearray)):
            try:
                payload = json.loads(data.decode("utf-8"))
                message = payload.get("error", {}).get("message", "")
            except (ValueError, UnicodeDecodeError):
                message = data.decode("utf-8", "replace")[:500]
        cls = RateLimitError if status == 429 else ApiError
        return cls(status, message or "request failed", payload)

    @staticmethod
    def _backoff(attempt: int, headers: dict[str, str], error: ApiError) -> float:
        """Exponential backoff with jitter, preferring the server's own hint."""
        retry_after = headers.get("Retry-After") or headers.get("retry-after")
        if retry_after:
            try:
                return min(float(retry_after), 60.0)
            except ValueError:
                pass
        for detail in error.payload.get("error", {}).get("details", []):
            delay = detail.get("retryDelay")
            if isinstance(delay, str) and delay.endswith("s"):
                try:
                    return min(float(delay[:-1]), 60.0)
                except ValueError:
                    pass
        return min(2.0 ** attempt, 32.0) + random.uniform(0, 0.5)

    def generate(self, prompt: str | None = None, **kwargs: Any) -> GeminiResponse:
        """Run one ``generateContent`` call and return the parsed response."""
        model = kwargs.pop("model", None) or self.model
        allow_empty = kwargs.pop("allow_empty", False)
        grounded = bool(kwargs.get("google_search"))
        payload = self.build_payload(prompt, model=model, **kwargs)
        with _grounding_quota_hint(grounded):
            data = self._post(self._url(model, "generateContent"), payload)
        parsed = json.loads(data.decode("utf-8"))
        return self._parse(parsed, model, allow_empty=allow_empty)

    def stream(self, prompt: str | None = None, **kwargs: Any) -> Iterator[str]:
        """Yield text chunks from ``streamGenerateContent`` (SSE)."""
        model = kwargs.pop("model", None) or self.model
        kwargs.pop("allow_empty", None)
        grounded = bool(kwargs.get("google_search"))
        payload = self.build_payload(prompt, model=model, **kwargs)
        url = self._url(model, "streamGenerateContent", "?alt=sse")
        with _grounding_quota_hint(grounded):
            response = self._post(url, payload, stream=True)
        for line in response:
            if isinstance(line, (bytes, bytearray)):
                line = line.decode("utf-8")
            line = line.strip()
            if not line.startswith("data:"):
                continue
            chunk = line[len("data:"):].strip()
            if not chunk or chunk == "[DONE]":
                continue
            try:
                event = json.loads(chunk)
            except ValueError:
                continue
            for part in _iter_parts(event):
                if part.get("thought"):
                    continue
                if "text" in part:
                    yield part["text"]

    def call_with_tools(
        self,
        prompt: str,
        *,
        functions: Sequence[dict[str, Any]],
        handlers: dict[str, Callable[..., Any]],
        max_rounds: int = 5,
        **kwargs: Any,
    ) -> GeminiResponse:
        """Run the function-calling loop until the model answers in text.

        ``functions`` are Gemini ``functionDeclarations``; ``handlers`` maps a
        declaration name to the Python callable that implements it.
        """
        model = kwargs.pop("model", None) or self.model
        contents: list[dict[str, Any]] = [{"role": "user", "parts": [{"text": prompt}]}]
        tools = [{"functionDeclarations": list(functions)}]
        response = None
        for _ in range(max_rounds):
            response = self.generate(
                contents=contents, tools=tools, model=model, allow_empty=True, **kwargs
            )
            if not response.function_calls:
                return response
            contents.append(_model_turn(response))
            replies = []
            for call in response.function_calls:
                handler = handlers.get(call.name)
                if handler is None:
                    result: Any = {"error": f"no handler registered for {call.name!r}"}
                else:
                    try:
                        result = handler(**call.args)
                    except Exception as exc:  # surfaced to the model, not swallowed
                        result = {"error": f"{type(exc).__name__}: {exc}"}
                replies.append(
                    {"functionResponse": {"name": call.name, "response": {"result": result}}}
                )
            contents.append({"role": "user", "parts": replies})
        assert response is not None
        return response

    def list_models(self) -> list[dict[str, Any]]:
        """Return the models this key can see (``ListModels``).

        Note that presence here is not proof of access: retired models stay
        listed but answer ``generateContent`` with 404 for newer keys.
        """
        status, data = self._transport.get(
            f"{API_ROOT}/models?pageSize=1000", headers=self._headers(), timeout=self.timeout
        )
        if status != 200:
            raise self._to_error(status, data)
        return json.loads(data.decode("utf-8")).get("models", [])

    # ----------------------------------------------------------------- parse

    def _parse(self, data: dict[str, Any], model: str, *, allow_empty: bool = False) -> GeminiResponse:
        candidates = data.get("candidates") or []
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason")
            raise EmptyResponseError(
                f"no candidates returned{f' (blocked: {reason})' if reason else ''}",
                usage=data.get("usageMetadata", {}),
            )
        candidate = candidates[0]
        finish = candidate.get("finishReason")
        texts: list[str] = []
        calls: list[FunctionCall] = []
        for part in candidate.get("content", {}).get("parts", []) or []:
            if part.get("thought"):
                continue  # reasoning tokens, not the answer
            if "text" in part:
                texts.append(part["text"])
            if "functionCall" in part:
                fc = part["functionCall"]
                calls.append(FunctionCall(name=fc.get("name", ""), args=fc.get("args") or {}))

        text = "".join(texts)
        usage = data.get("usageMetadata", {}) or {}
        if not text and not calls and not allow_empty:
            raise EmptyResponseError(
                _empty_hint(finish, usage), finish_reason=finish, usage=usage
            )

        url_meta = candidate.get("urlContextMetadata", {}) or {}
        retrieved = [
            RetrievedUrl(url=m.get("retrievedUrl", ""), status=m.get("urlRetrievalStatus", ""))
            for m in url_meta.get("urlMetadata", []) or []
        ]

        grounding = candidate.get("groundingMetadata", {}) or {}
        sources = []
        for chunk in grounding.get("groundingChunks", []) or []:
            web = chunk.get("web") or {}
            if web.get("uri"):
                sources.append(Source(title=web.get("title") or web["uri"], uri=web["uri"]))
        return GeminiResponse(
            text=text,
            model=data.get("modelVersion") or model,
            finish_reason=finish,
            function_calls=calls,
            sources=sources,
            search_queries=list(grounding.get("webSearchQueries") or []),
            retrieved_urls=retrieved,
            usage=usage,
            raw=data,
        )


@contextlib.contextmanager
def _grounding_quota_hint(grounded: bool):
    """Say which quota ran out when a *grounded* call is rate-limited.

    Google Search grounding is metered separately from ordinary generation, and
    on the free tier it runs out first — so the bare "you exceeded your current
    quota" reads as if the whole key is dead when plain calls still work.
    """
    try:
        yield
    except RateLimitError as exc:
        if not grounded:
            raise
        raise RateLimitError(
            exc.status,
            exc.message
            + " | This call used Google Search grounding, which is metered "
              "separately from ordinary generation: ungrounded calls may still "
              "succeed. Wait for the grounding quota to reset, or enable "
              "billing at https://aistudio.google.com/apikey .",
            exc.payload,
        ) from exc


def _empty_hint(finish: str | None, usage: dict[str, Any]) -> str:
    """Explain an empty answer in terms the caller can act on."""
    if finish == "MAX_TOKENS":
        thoughts = usage.get("thoughtsTokenCount")
        if thoughts:
            return (
                f"the model spent the whole output budget on reasoning "
                f"({thoughts} thinking tokens) and produced no answer — raise "
                f"max_output_tokens or pass thinking_level='low'"
            )
        return "hit max_output_tokens before producing any text — raise max_output_tokens"
    if finish in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"):
        return f"the response was blocked (finishReason={finish})"
    return f"the model returned no text (finishReason={finish})"


def _iter_parts(event: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for candidate in event.get("candidates") or []:
        yield from candidate.get("content", {}).get("parts", []) or []


def _model_turn(response: GeminiResponse) -> dict[str, Any]:
    """Rebuild the model's turn so a tool result can be appended after it."""
    parts: list[dict[str, Any]] = []
    for candidate in response.raw.get("candidates") or []:
        for part in candidate.get("content", {}).get("parts", []) or []:
            parts.append(part)
        break
    return {"role": "model", "parts": parts or [{"text": response.text}]}
