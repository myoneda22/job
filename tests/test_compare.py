from __future__ import annotations

import json

import pytest

from conftest import FakeTransport, text_response
from gemini_link.claude import ClaudeClient
from gemini_link.compare import compare
from gemini_link.config import Settings
from gemini_link.errors import ApiError, EmptyResponseError
from gemini_link.gemini import GeminiClient

JUDGE = {
    "verdict": "conflict",
    "agreements": ["どちらも28卒採用を実施していると述べている"],
    "conflicts": [{"topic": "応募締切", "answer_a": "3月末", "answer_b": "4月末"}],
    "unverified": ["初任給の記載はGemini側のみ"],
    "summary": "採用実施の点は一致するが、締切が食い違うため公式サイトの確認が必要。",
}


def _claude(transport, settings, text="Claudeの回答"):
    transport.queue_json({
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "model": "claude-sonnet-5",
    })
    return ClaudeClient(api_key="test-anthropic-key", settings=settings, transport=transport)


def test_both_answer_then_a_judge_reports_the_conflict(settings, transport):
    transport.queue_json(text_response("Geminiの回答"))
    transport.queue_json(text_response(json.dumps(JUDGE, ensure_ascii=False)))
    gemini = GeminiClient(settings=settings, transport=transport, sleep=lambda _: None)

    claude_transport = FakeTransport()
    claude = _claude(claude_transport, settings)

    result = compare("A社の28卒締切は？", settings=settings,
                     gemini_client=gemini, claude_client=claude)

    assert result.verdict == "conflict"
    assert result.conflicts[0]["topic"] == "応募締切"
    assert result.gemini.text == "Geminiの回答"
    assert result.claude.text == "Claudeの回答"
    assert result.gemini.ok and result.claude.ok


def test_the_judge_never_learns_which_model_wrote_which_answer(settings, transport):
    # Neutral answer bodies, so any provider name in the prompt would have to
    # come from the labelling rather than from the answers themselves.
    transport.queue_json(text_response("締切は3月末です"))
    transport.queue_json(text_response(json.dumps(JUDGE, ensure_ascii=False)))
    gemini = GeminiClient(settings=settings, transport=transport, sleep=lambda _: None)
    compare("q", settings=settings, gemini_client=gemini,
            claude_client=_claude(FakeTransport(), settings, "締切は4月末です"))

    judge_prompt = transport.requests[-1]["body"]["contents"][0]["parts"][0]["text"]
    judge_system = transport.requests[-1]["body"]["systemInstruction"]["parts"][0]["text"]
    assert "回答A" in judge_prompt and "回答B" in judge_prompt
    for name in ("Gemini", "Claude", "gemini", "claude"):
        assert name not in judge_prompt
        assert name not in judge_system


def test_without_an_anthropic_key_it_degrades_and_says_so(settings, transport):
    transport.queue_json(text_response("Geminiだけの回答"))
    gemini = GeminiClient(settings=settings, transport=transport, sleep=lambda _: None)

    result = compare("q", settings=settings, gemini_client=gemini)

    assert result.verdict == "single"
    assert result.gemini.ok
    assert not result.claude.ok
    assert "ANTHROPIC_API_KEY" in result.claude.error
    assert "相互検証できていません" in result.summary
    # Only the one answer was requested — no judge call was made.
    assert len(transport.requests) == 1


def test_a_failing_claude_call_does_not_lose_the_gemini_answer(settings, transport):
    transport.queue_json(text_response("Geminiの回答"))
    gemini = GeminiClient(settings=settings, transport=transport, sleep=lambda _: None)

    claude_transport = FakeTransport().queue_error(401, "invalid x-api-key")
    claude = ClaudeClient(api_key="bad", settings=settings, transport=claude_transport)

    result = compare("q", settings=settings, gemini_client=gemini, claude_client=claude)

    assert result.verdict == "single"
    assert result.gemini.text == "Geminiの回答"
    assert "invalid x-api-key" in result.claude.error


def test_a_failing_judge_still_returns_both_answers(settings, transport):
    transport.queue_json(text_response("Geminiの回答"))
    for _ in range(settings.max_retries + 1):
        transport.queue_error(429, "quota")
    gemini = GeminiClient(settings=settings, transport=transport, sleep=lambda _: None)

    result = compare("q", settings=settings, gemini_client=gemini,
                     claude_client=_claude(FakeTransport(), settings))

    assert result.verdict == "unjudged"
    assert result.gemini.ok and result.claude.ok
    assert "RateLimitError" in result.summary


def test_to_text_puts_conflicts_before_agreements(settings, transport):
    transport.queue_json(text_response("Geminiの回答"))
    transport.queue_json(text_response(json.dumps(JUDGE, ensure_ascii=False)))
    gemini = GeminiClient(settings=settings, transport=transport, sleep=lambda _: None)
    report = compare("q", settings=settings, gemini_client=gemini,
                     claude_client=_claude(FakeTransport(), settings)).to_text()

    assert report.index("不一致（要確認）") < report.index("両モデル一致")
    assert "応募締切" in report
    assert "❌" in report


def test_to_dict_is_json_serialisable(settings, transport):
    transport.queue_json(text_response("Geminiの回答", candidates=[{
        "content": {"parts": [{"text": "Geminiの回答"}]},
        "groundingMetadata": {
            "groundingChunks": [{"web": {"uri": "https://example.com", "title": "例"}}]
        },
    }]))
    transport.queue_json(text_response(json.dumps(JUDGE, ensure_ascii=False)))
    gemini = GeminiClient(settings=settings, transport=transport, sleep=lambda _: None)
    result = compare("q", settings=settings, gemini_client=gemini,
                     claude_client=_claude(FakeTransport(), settings), google_search=True)

    dumped = json.loads(json.dumps(result.to_dict(), ensure_ascii=False))
    assert dumped["gemini"]["sources"][0]["uri"] == "https://example.com"


def test_claude_client_sends_the_documented_headers(settings):
    transport = FakeTransport()
    claude = _claude(transport, settings, "hi")
    claude.generate("q", system="be terse", max_tokens=64)
    sent = transport.requests[-1]
    assert sent["headers"]["x-api-key"] == "test-anthropic-key"
    assert sent["headers"]["anthropic-version"] == "2023-06-01"
    assert sent["body"]["system"] == "be terse"
    assert sent["body"]["max_tokens"] == 64
    assert "test-anthropic-key" not in sent["url"]


def test_claude_error_and_empty_paths(settings):
    bad = FakeTransport().queue_error(529, "overloaded")
    with pytest.raises(ApiError, match="overloaded"):
        ClaudeClient(api_key="k", settings=settings, transport=bad).generate("q")

    empty = FakeTransport()
    empty.queue_json({"content": [], "stop_reason": "max_tokens"})
    with pytest.raises(EmptyResponseError, match="max_tokens"):
        ClaudeClient(api_key="k", settings=settings, transport=empty).generate("q")
