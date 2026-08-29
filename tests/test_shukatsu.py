from __future__ import annotations

import datetime as dt
import json

import pytest

from conftest import text_response
from gemini_link.errors import GeminiLinkError
from gemini_link.gemini import GeminiClient
from gemini_link.shukatsu import UNKNOWN, research_company, research_many

TODAY = dt.date(2026, 8, 29)

FINDINGS = {
    "recruiting_status": "28卒の本選考エントリーを受付中",
    "entry_period": "2026年3月1日エントリー開始、2026年5月31日締切",
    "selection_flow": "ES→Webテスト→面接3回",
    "internship": "2026年夏に5daysインターンを実施",
    "english_requirement": "TOEIC730以上が目安、帰国子女向けの通年採用枠あり",
    "compensation": "初任給30万円",
    "recent_news": "2026年6月に初任給を引き上げ",
    "confidence": "high",
}


def _queue_research(transport, findings=None, sources=True):
    """Queue the grounded call, then the structuring call."""
    grounded = text_response("調査結果の本文")
    if sources:
        grounded["candidates"][0]["groundingMetadata"] = {
            "webSearchQueries": ["A社 28卒 採用"],
            "groundingChunks": [
                {"web": {"uri": "https://a.example.com/recruit", "title": "A社 採用情報"}},
                {"web": {"uri": "https://b.example.com/news", "title": "プレスリリース"}},
            ],
        }
    transport.queue_json(grounded)
    transport.queue_json(
        text_response(json.dumps(findings if findings is not None else FINDINGS, ensure_ascii=False))
    )


def test_research_makes_a_grounded_call_then_a_structuring_call(client, transport):
    _queue_research(transport)
    result = research_company("A社", grad_year=2028, client=client, today=TODAY)

    first, second = transport.requests
    # Call 1 grounds against Google Search and asks for no schema.
    assert first["body"]["tools"] == [{"google_search": {}}]
    assert "responseSchema" not in first["body"]["generationConfig"]
    # Call 2 asks for the schema and must NOT search — the two are exclusive.
    assert "tools" not in second["body"]
    assert second["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert "recruiting_status" in second["body"]["generationConfig"]["responseSchema"]["properties"]
    # The structuring call only sees what the grounded call retrieved.
    assert "調査結果の本文" in second["body"]["contents"][0]["parts"][0]["text"]

    assert result.company == "A社"
    assert result.grad_year == 2028
    assert result.confidence == "high"
    assert result.researched_on == "2026-08-29"
    assert [s.uri for s in result.sources] == [
        "https://a.example.com/recruit", "https://b.example.com/news"
    ]


def test_the_prompt_carries_the_short_grad_year_and_today(client, transport):
    _queue_research(transport)
    research_company("A社", grad_year=2028, client=client, today=TODAY)
    prompt = transport.requests[0]["body"]["contents"][0]["parts"][0]["text"]
    assert "2028年卒" in prompt and "28卒" in prompt
    assert "2026-08-29" in prompt


def test_remarks_render_for_the_airtable_field(client, transport):
    _queue_research(transport)
    remarks = research_company("A社", grad_year=2028, client=client, today=TODAY).to_remarks()

    assert remarks.startswith("【28卒採用｜2026-08-29時点・Gemini調査】")
    assert "・採用状況: 28卒の本選考エントリーを受付中" in remarks
    assert "・英語/帰国子女: TOEIC730以上が目安、帰国子女向けの通年採用枠あり" in remarks
    assert "・情報の確度: high" in remarks
    assert "https://a.example.com/recruit" in remarks
    # Fields keep the declared order.
    assert remarks.index("採用状況") < remarks.index("エントリー時期") < remarks.index("初任給")


def test_unknown_fields_are_dropped_from_the_note(client, transport):
    findings = dict(FINDINGS, selection_flow=UNKNOWN, compensation=UNKNOWN, internship="")
    _queue_research(transport, findings)
    remarks = research_company("A社", client=client, today=TODAY).to_remarks()

    assert "選考フロー" not in remarks
    assert "初任給・待遇" not in remarks
    assert "インターン" not in remarks
    assert "採用状況" in remarks


def test_all_unknown_flags_low_confidence_and_asks_for_a_manual_check(client, transport):
    findings = {k: UNKNOWN for k in FINDINGS}
    findings["confidence"] = "high"  # the model's own claim must not survive this
    _queue_research(transport, findings)
    result = research_company("無名企業", client=client, today=TODAY)

    assert result.confidence == "low"
    assert "要手動確認" in result.to_remarks()


def test_remarks_can_be_truncated_to_fit_a_cell(client, transport):
    _queue_research(transport)
    result = research_company("A社", client=client, today=TODAY)
    short = result.to_remarks(max_chars=60)
    assert len(short) == 60
    assert short.endswith("…")


def test_missing_keys_in_the_model_output_become_unknown(client, transport):
    _queue_research(transport, {"recruiting_status": "受付中", "confidence": "medium"})
    result = research_company("A社", client=client, today=TODAY)
    assert result.fields["compensation"] == UNKNOWN
    assert result.fields["recruiting_status"] == "受付中"
    assert result.confidence == "medium"


def test_unparseable_structuring_output_names_the_company(client, transport):
    transport.queue_json(text_response("調査結果"))
    transport.queue_json(text_response("これはJSONではありません"))
    with pytest.raises(GeminiLinkError, match="A社"):
        research_company("A社", client=client, today=TODAY)


def test_a_json_array_is_rejected(client, transport):
    transport.queue_json(text_response("調査結果"))
    transport.queue_json(text_response("[1, 2]"))
    with pytest.raises(GeminiLinkError, match="expected a JSON object"):
        research_company("A社", client=client, today=TODAY)


def test_empty_company_name_is_rejected_before_any_call(client, transport):
    with pytest.raises(ValueError, match="must not be empty"):
        research_company("   ", client=client)
    assert transport.requests == []


def test_to_dict_includes_the_rendered_remarks(client, transport):
    _queue_research(transport)
    data = research_company("A社", client=client, today=TODAY).to_dict()
    round_tripped = json.loads(json.dumps(data, ensure_ascii=False))
    assert round_tripped["remarks"].startswith("【28卒採用")
    assert round_tripped["sources"][0]["title"] == "A社 採用情報"
    assert round_tripped["search_queries"] == ["A社 28卒 採用"]


def test_research_many_collects_failures_without_losing_the_rest(settings, transport):
    client = GeminiClient(settings=settings, transport=transport, sleep=lambda _: None)
    _queue_research(transport)                       # A社 succeeds
    transport.queue_json(text_response("調査結果"))   # B社 grounded call
    transport.queue_json(text_response("not json"))  # B社 structuring fails
    _queue_research(transport)                       # C社 succeeds

    results, failures = research_many(["A社", "B社", "C社"], client=client)

    assert [r.company for r in results] == ["A社", "C社"]
    assert len(failures) == 1
    assert failures[0][0] == "B社"
    assert "GeminiLinkError" in failures[0][1]


def test_research_many_can_raise_instead_of_collecting(settings, transport):
    client = GeminiClient(settings=settings, transport=transport, sleep=lambda _: None)
    transport.queue_json(text_response("調査結果"))
    transport.queue_json(text_response("not json"))
    with pytest.raises(GeminiLinkError):
        research_many(["B社"], client=client, on_error="raise")


# ------------------------------------------------- URL-based research path

from conftest import url_context_response  # noqa: E402
from gemini_link.errors import RetrievalError  # noqa: E402
from gemini_link.shukatsu import research_company_from_urls  # noqa: E402

URLS = ["https://a.example.com/recruit", "https://a.example.com/news"]


def test_url_research_reads_the_pages_then_structures_them(client, transport):
    transport.queue_json(url_context_response(
        "ページの内容", [(u, "URL_RETRIEVAL_STATUS_SUCCESS") for u in URLS]))
    transport.queue_json(text_response(json.dumps(FINDINGS, ensure_ascii=False)))

    result = research_company_from_urls("A社", URLS, grad_year=2028,
                                        client=client, today=TODAY)

    first, second = transport.requests
    assert first["body"]["tools"] == [{"url_context": {}}]
    assert "google_search" not in json.dumps(first["body"])
    for url in URLS:
        assert url in first["body"]["contents"][0]["parts"][0]["text"]
    # The structuring call sees only what was read off the pages.
    assert "tools" not in second["body"]
    assert "ページの内容" in second["body"]["contents"][0]["parts"][0]["text"]

    assert [s.uri for s in result.sources] == URLS
    assert result.confidence == "high"
    assert "・採用状況: 28卒の本選考エントリーを受付中" in result.to_remarks()


def test_url_research_refuses_when_a_page_could_not_be_read(client, transport):
    # This is the whole point: the model still returns fluent text, so only the
    # retrieval status stops an ungrounded answer being recorded as research.
    transport.queue_json(url_context_response("それらしい採用情報", [
        (URLS[0], "URL_RETRIEVAL_STATUS_SUCCESS"),
        (URLS[1], "URL_RETRIEVAL_STATUS_ERROR"),
    ]))
    with pytest.raises(RetrievalError) as excinfo:
        research_company_from_urls("A社", URLS, client=client, today=TODAY)
    assert URLS[1] in str(excinfo.value)
    # It must not have gone on to structure and store the ungrounded answer.
    assert len(transport.requests) == 1


def test_url_research_refuses_when_no_retrieval_was_reported(client, transport):
    transport.queue_json(text_response("記憶から答えた内容"))
    with pytest.raises(RetrievalError, match="not grounded"):
        research_company_from_urls("A社", URLS, client=client, today=TODAY)
    assert len(transport.requests) == 1


def test_url_research_requires_at_least_one_url(client, transport):
    with pytest.raises(ValueError, match="at least one URL"):
        research_company_from_urls("A社", [], client=client)
    assert transport.requests == []


def test_url_research_rejects_an_empty_company_name(client, transport):
    with pytest.raises(ValueError, match="must not be empty"):
        research_company_from_urls("  ", URLS, client=client)
    assert transport.requests == []


def test_url_research_only_cites_pages_it_actually_read(client, transport):
    # A page that failed cannot appear as a source; here all succeed but a
    # third URL the model volunteered is not in the request, so is not cited.
    transport.queue_json(url_context_response(
        "ページの内容", [(URLS[0], "URL_RETRIEVAL_STATUS_SUCCESS")]))
    transport.queue_json(text_response(json.dumps(FINDINGS, ensure_ascii=False)))
    result = research_company_from_urls("A社", [URLS[0]], client=client, today=TODAY)
    assert [s.uri for s in result.sources] == [URLS[0]]
    assert URLS[0] in result.to_remarks()
