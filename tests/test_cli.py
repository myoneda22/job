from __future__ import annotations

import json

import pytest

from conftest import FakeTransport, text_response
from gemini_link import cli
from gemini_link.gemini import GeminiClient


@pytest.fixture
def fake_cli(monkeypatch, settings, transport):
    """Point the CLI at the fake transport and a key-less environment."""
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    made = GeminiClient(settings=settings, transport=transport, sleep=lambda _: None)
    monkeypatch.setattr(cli, "GeminiClient", lambda **kw: made)
    return transport


def test_status_redacts_the_key(fake_cli, capsys):
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "test-gemini-key" not in out
    assert "gemini-3.7-flash" in out


def test_ask_prints_the_answer(fake_cli, capsys):
    fake_cli.queue_json(text_response("答えです"))
    assert cli.main(["ask", "質問", "です"]) == 0
    assert capsys.readouterr().out.strip() == "答えです"
    assert fake_cli.last_body["contents"][0]["parts"][0]["text"] == "質問 です"


def test_ask_json_mode_includes_usage(fake_cli, capsys):
    fake_cli.queue_json(text_response("答え"))
    cli.main(["ask", "q", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["text"] == "答え"
    assert payload["usage"]["totalTokenCount"] == 10


def test_ask_stream_writes_chunks(fake_cli, capsys):
    fake_cli.queue_sse([
        'data: {"candidates":[{"content":{"parts":[{"text":"あ"}]}}]}',
        'data: {"candidates":[{"content":{"parts":[{"text":"い"}]}}]}',
    ])
    assert cli.main(["ask", "q", "--stream"]) == 0
    assert capsys.readouterr().out.strip() == "あい"


def test_search_prints_sources(fake_cli, capsys):
    fake_cli.queue_json(text_response("回答", candidates=[{
        "content": {"parts": [{"text": "回答"}]},
        "groundingMetadata": {
            "groundingChunks": [{"web": {"uri": "https://ex.com", "title": "出典1"}}]
        },
    }]))
    assert cli.main(["search", "28卒", "締切"]) == 0
    out = capsys.readouterr().out
    assert "回答" in out
    assert "出典1: https://ex.com" in out
    assert fake_cli.last_body["tools"] == [{"google_search": {}}]


def test_company_prints_the_remarks_note(fake_cli, capsys):
    fake_cli.queue_json(text_response("調査本文"))
    fake_cli.queue_json(text_response(json.dumps(
        {"recruiting_status": "受付中", "confidence": "medium"}, ensure_ascii=False)))
    assert cli.main(["company", "A社", "--grad-year", "2028"]) == 0
    out = capsys.readouterr().out
    assert "【28卒採用" in out
    assert "・採用状況: 受付中" in out


def test_batch_reads_stdin_and_reports_failures(fake_cli, capsys, monkeypatch):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("A社\n\nB社\n"))
    fake_cli.queue_json(text_response("調査本文"))
    fake_cli.queue_json(text_response('{"recruiting_status": "受付中", "confidence": "high"}'))
    fake_cli.queue_json(text_response("調査本文"))
    fake_cli.queue_json(text_response("not json"))

    assert cli.main(["batch", "-"]) == 1  # non-zero because one company failed
    captured = capsys.readouterr()
    assert "===== A社 =====" in captured.out
    assert "[失敗] B社" in captured.err


def test_models_lists_only_generate_content_models(fake_cli, capsys):
    fake_cli.queue_json({"models": [
        {"name": "models/gemini-3.7-flash", "supportedGenerationMethods": ["generateContent"],
         "inputTokenLimit": 1048576, "outputTokenLimit": 65536},
        {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
    ]})
    assert cli.main(["models"]) == 0
    out = capsys.readouterr().out
    assert "gemini-3.7-flash" in out
    assert "text-embedding-004" not in out


def test_a_missing_key_exits_2_with_a_fixable_message(monkeypatch, capsys):
    from gemini_link.config import Settings
    monkeypatch.setattr(cli, "load_settings",
                        lambda: Settings(None, "m", None, "c", 5.0, 1))
    assert cli.main(["ask", "q"]) == 2
    err = capsys.readouterr().err
    assert "GEMINI_API_KEY" in err
    assert "aistudio.google.com" in err


def test_an_api_error_exits_1(fake_cli, capsys):
    fake_cli.queue_error(400, "Request contains an invalid argument.")
    assert cli.main(["ask", "q"]) == 1
    assert "invalid argument" in capsys.readouterr().err


def test_compare_exit_code_signals_a_conflict(fake_cli, capsys, monkeypatch, settings):
    from gemini_link.claude import ClaudeClient
    claude_transport = FakeTransport()
    claude_transport.queue_json({"content": [{"type": "text", "text": "別の回答"}],
                                 "stop_reason": "end_turn"})
    monkeypatch.setattr(settings.__class__, "has_anthropic", property(lambda self: True))
    monkeypatch.setattr(
        "gemini_link.compare.ClaudeClient",
        lambda **kw: ClaudeClient(api_key="k", settings=settings, transport=claude_transport),
    )
    fake_cli.queue_json(text_response("回答"))
    fake_cli.queue_json(text_response(json.dumps(
        {"verdict": "conflict", "summary": "食い違いあり",
         "conflicts": [{"topic": "締切", "answer_a": "3月", "answer_b": "4月"}]},
        ensure_ascii=False)))

    assert cli.main(["compare", "締切は？"]) == 1
    assert "❌" in capsys.readouterr().out
