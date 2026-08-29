"""Tests for the MCP server.

Skipped when the MCP SDK is absent — it is an optional extra, and the rest of
the package must stay installable without it.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from conftest import text_response
from gemini_link.gemini import GeminiClient

# Gate on the SDK itself rather than on our module: our module deliberately
# raises ImportError when the SDK is absent, and skipping on the dependency
# says plainly which package is missing.
pytest.importorskip("mcp", reason="the MCP SDK is not installed (pip install 'mcp>=2')")

from gemini_link import mcp_server  # noqa: E402


@pytest.fixture
def served(monkeypatch, settings, transport):
    client = GeminiClient(settings=settings, transport=transport, sleep=lambda _: None)
    monkeypatch.setattr(mcp_server, "get_client", lambda: client)
    monkeypatch.setattr(mcp_server, "load_settings", lambda: settings)
    return transport


def run(coro):
    return asyncio.run(coro)


def test_every_tool_is_registered():
    names = {t.name for t in run(mcp_server.server.list_tools())}
    assert names == {
        "gemini_generate",
        "gemini_search",
        "gemini_second_opinion",
        "gemini_research_company",
        "gemini_read_urls",
        "gemini_research_company_from_urls",
        "gemini_list_models",
        "gemini_status",
    }


def test_every_tool_describes_when_to_use_it():
    for tool in run(mcp_server.server.list_tools()):
        assert tool.description and len(tool.description) > 40, tool.name


def test_generate_returns_plain_text_and_does_not_search(served):
    served.queue_json(text_response("答え"))
    assert run(mcp_server.gemini_generate("質問")) == "答え"
    assert "tools" not in served.last_body


def test_search_appends_sources(served):
    served.queue_json(text_response("回答", candidates=[{
        "content": {"parts": [{"text": "回答"}]},
        "groundingMetadata": {
            "groundingChunks": [{"web": {"uri": "https://ex.com", "title": "出典"}}]
        },
    }]))
    out = run(mcp_server.gemini_search("28卒 締切"))
    assert "回答" in out
    assert "出典: https://ex.com" in out
    assert served.last_body["tools"] == [{"google_search": {}}]


def test_second_opinion_sends_both_the_question_and_the_draft(served):
    served.queue_json(text_response("要修正です"))
    out = run(mcp_server.gemini_second_opinion("締切は？", "3月末です"))
    prompt = served.last_body["contents"][0]["parts"][0]["text"]
    assert "締切は？" in prompt and "3月末です" in prompt
    assert served.last_body["tools"] == [{"google_search": {}}]
    assert "要修正です" in out


def test_second_opinion_can_skip_the_search(served):
    served.queue_json(text_response("ok"))
    run(mcp_server.gemini_second_opinion("q", "draft", search=False))
    assert "tools" not in served.last_body


def test_research_company_returns_both_the_note_and_the_json(served):
    served.queue_json(text_response("調査本文"))
    served.queue_json(text_response('{"recruiting_status": "受付中", "confidence": "high"}'))
    out = run(mcp_server.gemini_research_company("A社", grad_year=2028))

    assert "備考欄用テキスト" in out
    assert "・採用状況: 受付中" in out
    payload = json.loads(out.split("── 構造化データ ──\n", 1)[1])
    assert payload["company"] == "A社"
    assert payload["grad_year"] == 2028


def test_list_models_filters_to_text_models(served):
    served.queue_json({"models": [
        {"name": "models/gemini-3.7-flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/embedding-001", "supportedGenerationMethods": ["embedContent"]},
    ]})
    out = run(mcp_server.gemini_list_models())
    assert "gemini-3.7-flash" in out
    assert "embedding-001" not in out


def test_status_never_prints_the_key(served):
    out = run(mcp_server.gemini_status())
    assert "test-gemini-key" not in out
    assert "gemini-3.7-flash" in out
    assert "<unset>" in out  # no Anthropic key configured


def test_a_client_error_propagates_rather_than_being_swallowed(served):
    served.queue_error(400, "Request contains an invalid argument.")
    with pytest.raises(Exception, match="invalid argument"):
        run(mcp_server.gemini_generate("q"))


# ----------------------------------------------------- URL-grounded tools

from conftest import url_context_response  # noqa: E402


def test_read_urls_tool_is_registered_with_the_others():
    names = {t.name for t in run(mcp_server.server.list_tools())}
    assert "gemini_read_urls" in names
    assert "gemini_research_company_from_urls" in names


def test_read_urls_returns_the_answer_and_the_pages(served):
    served.queue_json(url_context_response(
        "ページの要約", [("https://a.example.com", "URL_RETRIEVAL_STATUS_SUCCESS")]))
    out = run(mcp_server.gemini_read_urls(["https://a.example.com"], "何が書いてある？"))
    assert "ページの要約" in out
    assert "実際に読んだページ" in out
    assert served.last_body["tools"] == [{"url_context": {}}]


def test_read_urls_flags_an_answer_that_was_not_actually_fetched(served):
    served.queue_json(url_context_response(
        "それらしい答え", [("https://a.example.com", "URL_RETRIEVAL_STATUS_ERROR")]))
    out = run(mcp_server.gemini_read_urls(["https://a.example.com"], "q"))
    assert "信頼できません" in out
    assert "記憶で補った" in out
    assert "https://a.example.com" in out


def test_read_urls_rejects_an_empty_url_list(served):
    assert "URLを1つ以上" in run(mcp_server.gemini_read_urls([], "q"))


def test_research_from_urls_returns_note_and_json(served):
    served.queue_json(url_context_response(
        "ページ内容", [("https://a.example.com/recruit", "URL_RETRIEVAL_STATUS_SUCCESS")]))
    served.queue_json(text_response('{"recruiting_status": "受付中", "confidence": "high"}'))
    out = run(mcp_server.gemini_research_company_from_urls(
        "A社", ["https://a.example.com/recruit"], grad_year=2028))
    assert "備考欄用テキスト" in out
    payload = json.loads(out.split("── 構造化データ ──\n", 1)[1])
    assert payload["sources"][0]["uri"] == "https://a.example.com/recruit"
