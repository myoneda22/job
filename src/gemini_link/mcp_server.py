"""An MCP server that lets Claude Code call Gemini.

Run it over stdio and register it in ``.mcp.json`` (see ``.mcp.json.example``).
Claude then gets a second opinion, a Google-grounded search, and the 就活
company research as ordinary tools.

Every tool call does blocking HTTP, so each one is handed to a worker thread —
the MCP event loop stays responsive while a Gemini call is in flight.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from .config import load_settings, redact
from .gemini import GeminiClient
from .shukatsu import research_company, research_company_from_urls

_MISSING_SDK = (
    "The MCP SDK is not installed. Install it with:  pip install 'mcp>=2'  "
    "(or:  pip install -e '.[mcp]')"
)

try:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer as _Server
except ModuleNotFoundError:  # pragma: no cover - depends on installed mcp
    try:  # mcp < 2.0, where the class was still called FastMCP
        from mcp.server.fastmcp import FastMCP as _Server
    except ModuleNotFoundError as exc:  # pragma: no cover
        # ImportError, not SystemExit: this module is imported by tests and by
        # callers that can cope without it, and a bare SystemExit at import
        # time takes the whole interpreter down with it.
        raise ImportError(_MISSING_SDK) from exc

server = _Server(
    name="gemini-link",
    instructions=(
        "Call Gemini from inside Claude Code. Use gemini_search for questions "
        "needing fresh web facts with citations, gemini_second_opinion to have "
        "another model check an answer before you rely on it, and "
        "gemini_research_company for Japanese new-graduate hiring research."
    ),
)

_client: GeminiClient | None = None


def get_client() -> GeminiClient:
    """Build the client on first use so an unconfigured key fails per-call.

    Constructing at import time would make the whole server fail to start, and
    Claude Code would just show it as disconnected with no explanation.
    """
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client


def _format_sources(sources: list[Any]) -> str:
    if not sources:
        return ""
    lines = ["", "── 出典 ──"]
    lines += [f"- {s.title}: {s.uri}" for s in sources]
    return "\n".join(lines)


@server.tool(
    description=(
        "Ask Gemini a question and get its plain-text answer. Use this for a "
        "quick generation from a different model family; it does NOT search the "
        "web — use gemini_search when the answer depends on current facts."
    )
)
async def gemini_generate(
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_output_tokens: int = 4096,
) -> str:
    def run() -> str:
        resp = get_client().generate(
            prompt,
            system=system,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        return resp.text

    return await asyncio.to_thread(run)


@server.tool(
    description=(
        "Answer a question using Gemini with Google Search grounding, and "
        "return the answer followed by the source URLs it is based on. Use for "
        "anything time-sensitive: deadlines, prices, current status, news."
    )
)
async def gemini_search(query: str, model: str | None = None) -> str:
    def run() -> str:
        resp = get_client().generate(
            query,
            google_search=True,
            model=model,
            temperature=0,
            max_output_tokens=8192,
            thinking_level="low",
        )
        return resp.text + _format_sources(resp.sources)

    return await asyncio.to_thread(run)


@server.tool(
    description=(
        "Have Gemini independently review an answer you have already drafted. "
        "Returns Gemini's verdict on whether the answer holds up, what is wrong "
        "or unsupported, and what is missing. Use before relying on a claim that "
        "would be costly to get wrong."
    )
)
async def gemini_second_opinion(
    question: str,
    draft_answer: str,
    search: bool = True,
) -> str:
    system = (
        "あなたは厳格なレビュアーです。提示された『質問』と『別のAIによる回答案』を読み、"
        "回答案が正しいかを独立に検証してください。同意する点、誤り・根拠不足の点、"
        "抜けている点を分けて簡潔に述べ、最後に『採用可／要修正／不可』で結論を書いてください。"
        "回答案に引きずられず、自分で確かめた事実のみを根拠にしてください。"
    )
    prompt = f"# 質問\n{question}\n\n# 別のAIによる回答案\n{draft_answer}"

    def run() -> str:
        resp = get_client().generate(
            prompt,
            system=system,
            google_search=search,
            temperature=0,
            max_output_tokens=8192,
            thinking_level="low",
        )
        return resp.text + _format_sources(resp.sources)

    return await asyncio.to_thread(run)


@server.tool(
    description=(
        "Research a Japanese company's new-graduate hiring for a given "
        "graduation year (default 2028 / 28卒) using Google Search, and return "
        "both a ready-to-paste 備考 note for Airtable and the structured "
        "findings as JSON with source URLs."
    )
)
async def gemini_research_company(company: str, grad_year: int = 2028) -> str:
    def run() -> str:
        result = research_company(company, grad_year=grad_year, client=get_client())
        return (
            "── 備考欄用テキスト ──\n"
            f"{result.to_remarks()}\n\n"
            "── 構造化データ ──\n"
            f"{json.dumps(result.to_dict(), ensure_ascii=False, indent=2)}"
        )

    return await asyncio.to_thread(run)


@server.tool(
    description=(
        "Have Gemini fetch and read specific web pages, then answer a question "
        "using only what those pages say. Use instead of gemini_search when you "
        "already know which pages matter, or when search grounding is "
        "unavailable. Fails loudly rather than answering from memory if a page "
        "cannot be fetched — so a successful reply is genuinely page-grounded."
    )
)
async def gemini_read_urls(urls: list[str], question: str) -> str:
    if not urls:
        return "エラー: URLを1つ以上指定してください。"

    listed = "\n".join(urls)
    system = (
        "指定されたURLのページを実際に読み、そこに書かれている内容だけを使って答えてください。"
        "ページを取得できなかった場合、記憶や一般知識で補ってはいけません。"
        "ページに書かれていない項目は「不明」と明記してください。"
    )

    def run() -> str:
        resp = get_client().generate(
            f"{listed}\n\n{question}",
            system=system,
            url_context=True,
            temperature=0,
            max_output_tokens=8192,
            thinking_level="low",
        )
        failures = resp.retrieval_failures
        if failures:
            listed_failures = "\n".join(f"- {u.url} ({u.status})" for u in failures)
            return (
                "取得できなかったページがあるため、この回答は信頼できません。\n"
                "（取得失敗時、モデルは記憶で補った回答を返すことがあります）\n\n"
                f"取得失敗:\n{listed_failures}\n\n"
                f"参考（信頼しないでください）:\n{resp.text}"
            )
        read = "\n".join(f"- {u.url}" for u in resp.retrieved_urls)
        return f"{resp.text}\n\n── 実際に読んだページ ──\n{read}"

    return await asyncio.to_thread(run)


@server.tool(
    description=(
        "Research a company's new-graduate hiring by reading specific pages you "
        "supply (its recruit page, a press release) rather than by searching. "
        "Use when gemini_research_company is blocked by the search-grounding "
        "quota. Refuses to return findings unless every page was actually read."
    )
)
async def gemini_research_company_from_urls(
    company: str, urls: list[str], grad_year: int = 2028
) -> str:
    def run() -> str:
        result = research_company_from_urls(
            company, urls, grad_year=grad_year, client=get_client()
        )
        return (
            "── 備考欄用テキスト ──\n"
            f"{result.to_remarks()}\n\n"
            "── 構造化データ ──\n"
            f"{json.dumps(result.to_dict(), ensure_ascii=False, indent=2)}"
        )

    return await asyncio.to_thread(run)


@server.tool(
    description=(
        "List the Gemini models this API key can see, with their token limits. "
        "Note that a listed model can still refuse generateContent with 404 if "
        "it has been retired for newly issued keys."
    )
)
async def gemini_list_models(text_only: bool = True) -> str:
    def run() -> str:
        models = get_client().list_models()
        lines = []
        for m in models:
            name = m.get("name", "").replace("models/", "")
            methods = m.get("supportedGenerationMethods", [])
            if text_only and "generateContent" not in methods:
                continue
            lines.append(
                f"{name}  in={m.get('inputTokenLimit')} out={m.get('outputTokenLimit')}"
            )
        return "\n".join(lines) or "no models returned"

    return await asyncio.to_thread(run)


@server.tool(
    description=(
        "Report how this server is configured: which Gemini model is the "
        "default and whether the API keys are present. Keys are redacted."
    )
)
async def gemini_status() -> str:
    settings = load_settings()
    return (
        f"gemini model : {settings.gemini_model}\n"
        f"GEMINI_API_KEY : {redact(settings.gemini_api_key)}\n"
        f"ANTHROPIC_API_KEY : {redact(settings.anthropic_api_key)}\n"
        f"timeout : {settings.timeout}s  retries : {settings.max_retries}"
    )


def main() -> None:
    """Console-script entry point: serve over stdio."""
    server.run("stdio")


if __name__ == "__main__":
    main()
