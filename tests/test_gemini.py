from __future__ import annotations

import json

import pytest

from conftest import function_call_response, text_response, url_context_response
from gemini_link.errors import ApiError, EmptyResponseError, RateLimitError, RetrievalError
from gemini_link.gemini import GeminiClient


# ----------------------------------------------------------------- request shape

def test_api_key_travels_in_a_header_never_in_the_url(client, transport):
    transport.queue_json(text_response("hi"))
    client.generate("hello")
    sent = transport.requests[-1]
    assert sent["headers"]["x-goog-api-key"] == "test-gemini-key"
    assert "test-gemini-key" not in sent["url"]


def test_prompt_becomes_a_user_turn(client, transport):
    transport.queue_json(text_response("hi"))
    client.generate("hello", system="be terse", temperature=0.2, max_output_tokens=99)
    body = transport.last_body
    assert body["contents"] == [{"role": "user", "parts": [{"text": "hello"}]}]
    assert body["systemInstruction"] == {"parts": [{"text": "be terse"}]}
    assert body["generationConfig"]["temperature"] == 0.2
    assert body["generationConfig"]["maxOutputTokens"] == 99


def test_google_search_is_sent_as_a_tool(client, transport):
    transport.queue_json(text_response("hi"))
    client.generate("hello", google_search=True)
    assert transport.last_body["tools"] == [{"google_search": {}}]


def test_response_schema_switches_on_json_mime(client, transport):
    transport.queue_json(text_response('{"a": 1}'))
    schema = {"type": "object", "properties": {"a": {"type": "integer"}}}
    resp = client.generate("hello", response_schema=schema)
    gen = transport.last_body["generationConfig"]
    assert gen["responseMimeType"] == "application/json"
    assert gen["responseSchema"] == schema
    assert resp.json() == {"a": 1}


def test_schema_plus_search_is_refused_with_a_usable_message(client):
    with pytest.raises(ValueError, match="cannot be combined with google_search"):
        client.build_payload("hi", google_search=True, json_output=True)


def test_thinking_level_for_gemini_3_family(client, transport):
    transport.queue_json(text_response("hi"))
    client.generate("hello", thinking_level="low")
    assert transport.last_body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}


def test_thinking_level_is_mapped_to_a_budget_on_2_5(client, transport):
    transport.queue_json(text_response("hi"))
    client.generate("hello", model="gemini-2.5-flash", thinking_level="low")
    assert transport.last_body["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 512}


def test_explicit_budget_wins_over_level(client):
    payload = client.build_payload("hi", thinking_level="high", thinking_budget=0)
    assert payload["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}


def test_no_thinking_config_when_not_asked(client):
    assert "thinkingConfig" not in client.build_payload("hi").get("generationConfig", {})


def test_prompt_or_contents_is_required(client):
    with pytest.raises(ValueError, match="prompt or contents"):
        client.build_payload()


# --------------------------------------------------------------- response parse

def test_thought_parts_are_excluded_from_the_answer(client, transport):
    transport.queue_json({
        "candidates": [{
            "content": {"parts": [
                {"text": "internal reasoning", "thought": True},
                {"text": "the answer"},
            ]},
            "finishReason": "STOP",
        }],
        "modelVersion": "gemini-3.7-flash",
    })
    assert client.generate("q").text == "the answer"


def test_multiple_text_parts_are_joined(client, transport):
    transport.queue_json({
        "candidates": [{"content": {"parts": [{"text": "ab"}, {"text": "cd"}]}}],
    })
    assert client.generate("q").text == "abcd"


def test_grounding_sources_and_queries_are_surfaced(client, transport):
    transport.queue_json(text_response("grounded", candidates=[{
        "content": {"parts": [{"text": "grounded"}]},
        "finishReason": "STOP",
        "groundingMetadata": {
            "webSearchQueries": ["28卒 採用"],
            "groundingChunks": [
                {"web": {"uri": "https://example.com/a", "title": "A社 採用"}},
                {"web": {"title": "no uri"}},
            ],
        },
    }]))
    resp = client.generate("q", google_search=True)
    assert resp.search_queries == ["28卒 採用"]
    assert [(s.title, s.uri) for s in resp.sources] == [("A社 採用", "https://example.com/a")]


def test_function_calls_are_parsed(client, transport):
    transport.queue_json({"candidates": [{
        "content": {"parts": [{"functionCall": {"name": "lookup", "args": {"id": 7}}}]},
        "finishReason": "STOP",
    }]})
    resp = client.generate("q", allow_empty=True)
    assert resp.function_calls[0].name == "lookup"
    assert resp.function_calls[0].args == {"id": 7}


def test_json_helper_strips_a_code_fence(client, transport):
    transport.queue_json(text_response('```json\n{"ok": true}\n```'))
    assert client.generate("q").json() == {"ok": True}


# ------------------------------------------------------------------- empty text

def test_thinking_that_eats_the_budget_gets_an_actionable_error(client, transport):
    transport.queue_json({
        "candidates": [{"content": {"parts": [{"text": "t", "thought": True}]},
                        "finishReason": "MAX_TOKENS"}],
        "usageMetadata": {"thoughtsTokenCount": 512},
    })
    with pytest.raises(EmptyResponseError) as excinfo:
        client.generate("q")
    assert "thinking tokens" in str(excinfo.value)
    assert "max_output_tokens" in str(excinfo.value)
    assert excinfo.value.finish_reason == "MAX_TOKENS"


def test_safety_block_is_reported_as_such(client, transport):
    transport.queue_json({"candidates": [{"content": {"parts": []}, "finishReason": "SAFETY"}]})
    with pytest.raises(EmptyResponseError, match="blocked"):
        client.generate("q")


def test_no_candidates_reports_the_prompt_block_reason(client, transport):
    transport.queue_json({"candidates": [], "promptFeedback": {"blockReason": "OTHER"}})
    with pytest.raises(EmptyResponseError, match="OTHER"):
        client.generate("q")


def test_allow_empty_suppresses_the_error(client, transport):
    transport.queue_json({"candidates": [{"content": {"parts": []}, "finishReason": "STOP"}]})
    assert client.generate("q", allow_empty=True).text == ""


# ----------------------------------------------------------------------- retry

def test_429_is_retried_then_succeeds(client, transport):
    transport.queue_error(429, "quota").queue_json(text_response("recovered"))
    assert client.generate("q").text == "recovered"
    assert len(transport.requests) == 2


def test_retries_are_bounded_and_raise_rate_limit(settings, transport):
    slept: list[float] = []
    c = GeminiClient(settings=settings, transport=transport, sleep=slept.append)
    for _ in range(settings.max_retries + 1):
        transport.queue_error(429, "quota")
    with pytest.raises(RateLimitError) as excinfo:
        c.generate("q")
    assert excinfo.value.status == 429
    assert excinfo.value.retryable is True
    assert len(transport.requests) == settings.max_retries + 1
    assert len(slept) == settings.max_retries


def test_a_400_is_not_retried(client, transport):
    transport.queue_error(400, "Request contains an invalid argument.")
    with pytest.raises(ApiError) as excinfo:
        client.generate("q")
    assert excinfo.value.status == 400
    assert excinfo.value.retryable is False
    assert len(transport.requests) == 1


def test_retry_after_header_sets_the_delay(settings, transport):
    slept: list[float] = []
    c = GeminiClient(settings=settings, transport=transport, sleep=slept.append)
    transport.queue_error(429, "quota", headers={"Retry-After": "7"})
    transport.queue_json(text_response("ok"))
    c.generate("q")
    assert slept == [7.0]


def test_server_retry_delay_detail_is_honoured(settings, transport):
    slept: list[float] = []
    c = GeminiClient(settings=settings, transport=transport, sleep=slept.append)
    transport.queue_error(429, "quota", details=[{"retryDelay": "3s"}])
    transport.queue_json(text_response("ok"))
    c.generate("q")
    assert slept == [3.0]


def test_backoff_grows_and_is_capped(settings, transport):
    slept: list[float] = []
    c = GeminiClient(settings=settings, transport=transport, sleep=slept.append)
    for _ in range(settings.max_retries + 1):
        transport.queue_error(503, "unavailable")
    with pytest.raises(ApiError):
        c.generate("q")
    assert slept[0] < slept[-1]
    assert all(s <= 32.5 for s in slept)


def test_retired_model_404_surfaces_the_server_message(client, transport):
    transport.queue_error(404, "This model models/gemini-2.5-flash is no longer available")
    with pytest.raises(ApiError, match="no longer available"):
        client.generate("q", model="gemini-2.5-flash")


# ---------------------------------------------------------------------- stream

def test_stream_yields_text_and_skips_thoughts(client, transport):
    transport.queue_sse([
        'data: {"candidates":[{"content":{"parts":[{"text":"think","thought":true}]}}]}',
        'data: {"candidates":[{"content":{"parts":[{"text":"Hel"}]}}]}',
        "",
        'data: {"candidates":[{"content":{"parts":[{"text":"lo"}]}}]}',
        "data: [DONE]",
        "not-an-sse-line",
    ])
    assert "".join(client.stream("q")) == "Hello"
    assert transport.requests[-1]["url"].endswith("streamGenerateContent?alt=sse")
    assert transport.requests[-1]["stream"] is True


def test_stream_ignores_malformed_json_chunks(client, transport):
    transport.queue_sse(['data: {broken', 'data: {"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}'])
    assert "".join(client.stream("q")) == "ok"


# ------------------------------------------------------------- function calling

def test_call_with_tools_runs_the_handler_and_returns_the_final_text(client, transport):
    transport.queue_json(function_call_response("add", {"a": 1, "b": 2}))
    transport.queue_json(text_response("the sum is 3"))

    calls: list[tuple] = []

    def add(a: int, b: int) -> int:
        calls.append((a, b))
        return a + b

    resp = client.call_with_tools(
        "add 1 and 2",
        functions=[{"name": "add", "description": "add two numbers", "parameters": {}}],
        handlers={"add": add},
    )
    assert resp.text == "the sum is 3"
    assert calls == [(1, 2)]
    # The second request must replay the model turn, then the tool result.
    contents = transport.requests[1]["body"]["contents"]
    assert contents[1]["role"] == "model"
    assert contents[-1]["parts"][0]["functionResponse"]["response"]["result"] == 3


def test_a_raising_handler_is_reported_back_to_the_model(client, transport):
    transport.queue_json(function_call_response("boom"))
    transport.queue_json(text_response("recovered"))

    def boom():
        raise RuntimeError("nope")

    resp = client.call_with_tools("go", functions=[{"name": "boom"}], handlers={"boom": boom})
    assert resp.text == "recovered"
    reply = transport.requests[1]["body"]["contents"][-1]["parts"][0]
    assert "RuntimeError: nope" in reply["functionResponse"]["response"]["result"]["error"]


def test_an_unregistered_function_does_not_crash_the_loop(client, transport):
    transport.queue_json(function_call_response("ghost"))
    transport.queue_json(text_response("done"))
    client.call_with_tools("go", functions=[{"name": "ghost"}], handlers={})
    reply = transport.requests[1]["body"]["contents"][-1]["parts"][0]
    assert "no handler" in reply["functionResponse"]["response"]["result"]["error"]


def test_the_tool_loop_stops_at_max_rounds(client, transport):
    for _ in range(3):
        transport.queue_json(function_call_response("spin"))
    resp = client.call_with_tools(
        "go", functions=[{"name": "spin"}], handlers={"spin": lambda: "again"}, max_rounds=3
    )
    assert len(transport.requests) == 3
    assert resp.function_calls  # still asking, but the loop gave up rather than spinning


# ------------------------------------------------------------------ list models

def test_list_models_returns_the_model_array(client, transport):
    transport.queue_json({"models": [{"name": "models/gemini-3.7-flash"}]})
    assert client.list_models() == [{"name": "models/gemini-3.7-flash"}]


def test_list_models_raises_on_a_bad_key(client, transport):
    transport.queue_error(403, "API key not valid")
    with pytest.raises(ApiError, match="API key not valid"):
        client.list_models()


# ------------------------------------------------- grounding-specific quota

def test_a_grounded_429_names_the_grounding_quota(settings, transport):
    c = GeminiClient(settings=settings, transport=transport, sleep=lambda _: None)
    for _ in range(settings.max_retries + 1):
        transport.queue_error(429, "You exceeded your current quota")
    with pytest.raises(RateLimitError) as excinfo:
        c.generate("q", google_search=True)
    message = str(excinfo.value)
    assert "Google Search grounding" in message
    assert "ungrounded calls may still succeed" in message
    assert "You exceeded your current quota" in message  # server text is kept


def test_an_ungrounded_429_is_left_alone(settings, transport):
    c = GeminiClient(settings=settings, transport=transport, sleep=lambda _: None)
    for _ in range(settings.max_retries + 1):
        transport.queue_error(429, "You exceeded your current quota")
    with pytest.raises(RateLimitError) as excinfo:
        c.generate("q")
    assert "Google Search grounding" not in str(excinfo.value)


def test_a_grounded_400_is_not_rewritten(settings, transport):
    c = GeminiClient(settings=settings, transport=transport, sleep=lambda _: None)
    transport.queue_error(400, "Request contains an invalid argument.")
    with pytest.raises(ApiError) as excinfo:
        c.generate("q", google_search=True)
    assert "Google Search grounding" not in str(excinfo.value)


# ------------------------------------------------------------- url_context

def test_url_context_is_sent_as_a_tool(client, transport):
    transport.queue_json(text_response("ok"))
    client.generate("https://ex.com を読んで", url_context=True)
    assert transport.last_body["tools"] == [{"url_context": {}}]


def test_url_context_can_accompany_a_response_schema(client, transport):
    # Unlike google_search, url_context is not refused alongside structured
    # output — only the search-grounding combination is rejected.
    transport.queue_json(text_response('{"a": 1}'))
    payload = client.build_payload("q", url_context=True, json_output=True)
    assert payload["tools"] == [{"url_context": {}}]
    assert payload["generationConfig"]["responseMimeType"] == "application/json"


def test_retrieval_status_is_parsed(client, transport):
    transport.queue_json(url_context_response("読みました", [
        ("https://a.example.com", "URL_RETRIEVAL_STATUS_SUCCESS"),
        ("https://b.example.com", "URL_RETRIEVAL_STATUS_ERROR"),
    ]))
    resp = client.generate("q", url_context=True)
    assert [(u.url, u.ok) for u in resp.retrieved_urls] == [
        ("https://a.example.com", True),
        ("https://b.example.com", False),
    ]
    assert [u.url for u in resp.retrieval_failures] == ["https://b.example.com"]


def test_an_unknown_status_counts_as_a_failure(client, transport):
    # Fail closed: a status string we have never seen must not be read as success.
    transport.queue_json(url_context_response("答え", [
        ("https://a.example.com", "URL_RETRIEVAL_STATUS_SOMETHING_NEW"),
    ]))
    resp = client.generate("q", url_context=True)
    assert resp.retrieved_urls[0].ok is False
    with pytest.raises(RetrievalError):
        resp.require_retrieval()


def test_require_retrieval_passes_when_every_page_was_read(client, transport):
    transport.queue_json(url_context_response("読みました", [
        ("https://a.example.com", "URL_RETRIEVAL_STATUS_SUCCESS"),
    ]))
    resp = client.generate("q", url_context=True).require_retrieval()
    assert resp.text == "読みました"


def test_require_retrieval_names_the_pages_it_could_not_read(client, transport):
    transport.queue_json(url_context_response("それらしい答え", [
        ("https://a.example.com", "URL_RETRIEVAL_STATUS_SUCCESS"),
        ("https://b.example.com", "URL_RETRIEVAL_STATUS_ERROR"),
    ]))
    resp = client.generate("q", url_context=True)
    with pytest.raises(RetrievalError) as excinfo:
        resp.require_retrieval()
    assert "https://b.example.com" in str(excinfo.value)
    assert "https://a.example.com" not in str(excinfo.value)  # that one was fine
    assert "ungrounded" in str(excinfo.value)
    assert excinfo.value.failures == [("https://b.example.com", "URL_RETRIEVAL_STATUS_ERROR")]


def test_require_retrieval_rejects_an_answer_with_no_retrieval_at_all(client, transport):
    # The observed hallucination case: a fluent answer, no retrieval reported.
    transport.queue_json(text_response("自信ありげな答え"))
    resp = client.generate("q", url_context=True)
    assert resp.text == "自信ありげな答え"
    with pytest.raises(RetrievalError, match="not grounded"):
        resp.require_retrieval()


def test_an_ordinary_response_reports_no_retrieved_urls(client, transport):
    transport.queue_json(text_response("答え"))
    assert client.generate("q").retrieved_urls == []


# ------------------------------------------------------ transport failures

def test_a_socket_timeout_becomes_a_retryable_status_not_a_traceback(settings):
    """A read timeout must not escape as a raw socket error."""
    import urllib.error
    from gemini_link.gemini import Transport

    class TimingOutTransport(Transport):
        def __init__(self):
            self.calls = 0

        def request(self, url, *, headers, body, timeout, stream=False):
            self.calls += 1
            if self.calls == 1:
                return self._fail()
            return 200, {}, json.dumps(text_response("recovered")).encode()

        def _fail(self):
            from gemini_link.gemini import _network_failure
            return _network_failure(TimeoutError("The read operation timed out"))

    transport = TimingOutTransport()
    c = GeminiClient(settings=settings, transport=transport, sleep=lambda _: None)
    assert c.generate("q").text == "recovered"
    assert transport.calls == 2


def test_a_persistent_network_failure_raises_a_clean_api_error(settings):
    from gemini_link.gemini import Transport, _network_failure

    class DeadTransport(Transport):
        def request(self, url, *, headers, body, timeout, stream=False):
            return _network_failure(TimeoutError("The read operation timed out"))

    c = GeminiClient(settings=settings, transport=DeadTransport(), sleep=lambda _: None)
    with pytest.raises(ApiError) as excinfo:
        c.generate("q")
    assert excinfo.value.status == 504
    assert excinfo.value.retryable is True
    assert "TimeoutError" in str(excinfo.value)


def test_network_failure_helper_shapes_a_json_error_body(settings):
    from gemini_link.gemini import _network_failure
    status, headers, body = _network_failure(OSError("connection reset"))
    assert status == 504
    assert "connection reset" in json.loads(body)["error"]["message"]
