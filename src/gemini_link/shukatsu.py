"""Job-hunting (就活) company research, grounded in Google Search.

Feeds the existing Airtable workflow: given a company name and a graduation
year, produce the text that goes into the 備考 field of the 企業一覧 table,
with the source URLs the claim rests on.

Runs as two calls on purpose.  Google Search grounding and JSON-schema output
are mutually exclusive server-side, so the first call gathers grounded prose
plus citations and the second turns that prose into a fixed structure.  The
second call sees only what the first retrieved, which keeps ungrounded guesses
out of the structured record.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .config import Settings, load_settings
from .errors import GeminiLinkError
from .gemini import GeminiClient, Source

UNKNOWN = "不明"

_RESEARCH_SYSTEM = """\
あなたは日本の新卒採用に詳しいリサーチャーです。指定された企業の新卒採用について、
必ずGoogle検索で一次情報（企業の公式採用サイト、公式プレスリリース、マイナビ/リクナビ等の
公式掲載ページ）を確認してから答えてください。

厳守事項:
- 検索して確認できた事実のみを書くこと。推測で補完しない。
- 確認できなかった項目は「不明」と明記すること。曖昧にごまかさない。
- 日付・締切・金額は、出典に書かれている表現をそのまま引くこと。
- 情報がいつ時点のものかを明記すること。"""

_STRUCTURE_SYSTEM = """\
渡されたリサーチ結果を、指定のJSONスキーマに変換してください。
渡されたテキストに書かれていない情報を足してはいけません。
該当する記載がない項目は必ず "不明" という文字列にしてください。"""

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "recruiting_status": {"type": "string", "description": "対象年度卒の新卒採用の実施有無と受付状況"},
        "entry_period": {"type": "string", "description": "エントリー開始時期・応募締切"},
        "selection_flow": {"type": "string", "description": "選考フロー"},
        "internship": {"type": "string", "description": "インターンシップの有無と時期"},
        "english_requirement": {"type": "string", "description": "英語要件・TOEIC等・帰国子女/バイリンガル向け枠"},
        "compensation": {"type": "string", "description": "初任給・待遇"},
        "recent_news": {"type": "string", "description": "採用に関係する直近の動き"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": [
        "recruiting_status",
        "entry_period",
        "selection_flow",
        "internship",
        "english_requirement",
        "compensation",
        "recent_news",
        "confidence",
    ],
}

# Order matters: this is the order the 備考 field is rendered in.
_LABELS: list[tuple[str, str]] = [
    ("recruiting_status", "採用状況"),
    ("entry_period", "エントリー時期"),
    ("selection_flow", "選考フロー"),
    ("internship", "インターン"),
    ("english_requirement", "英語/帰国子女"),
    ("compensation", "初任給・待遇"),
    ("recent_news", "直近の動き"),
]


@dataclass
class CompanyResearch:
    company: str
    grad_year: int
    fields: dict[str, str] = field(default_factory=dict)
    confidence: str = "low"
    sources: list[Source] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    notes: str = ""
    researched_on: str = ""
    model: str = ""

    def to_remarks(self, *, max_sources: int = 4, max_chars: int | None = None) -> str:
        """Render the text for the Airtable 備考 field.

        Kept compact and prefixed with the research date, because the field is
        read at a glance in a table cell and a stale note is worse than none.
        """
        head = f"【{self.grad_year % 100}卒採用｜{self.researched_on}時点・Gemini調査】"
        lines = [head]
        for key, label in _LABELS:
            value = (self.fields.get(key) or UNKNOWN).strip()
            if value and value != UNKNOWN:
                lines.append(f"・{label}: {value}")
        if len(lines) == 1:
            lines.append(f"・確認できた公開情報がありませんでした（要手動確認）")
        lines.append(f"・情報の確度: {self.confidence}")
        if self.sources:
            urls = " / ".join(s.uri for s in self.sources[:max_sources])
            lines.append(f"・出典: {urls}")
        text = "\n".join(lines)
        if max_chars is not None and len(text) > max_chars:
            text = text[: max_chars - 1].rstrip() + "…"
        return text

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sources"] = [asdict(s) for s in self.sources]
        data["remarks"] = self.to_remarks()
        return data


def research_company(
    company: str,
    *,
    grad_year: int = 2028,
    client: GeminiClient | None = None,
    settings: Settings | None = None,
    today: _dt.date | None = None,
    extra_context: str = "",
) -> CompanyResearch:
    """Research one company's new-graduate hiring for ``grad_year``."""
    if not company.strip():
        raise ValueError("company must not be empty")

    settings = settings or load_settings()
    gemini = client or GeminiClient(settings=settings)
    today = today or _dt.date.today()
    short_year = grad_year % 100

    query = (
        f"{company} の {grad_year}年卒（{short_year}卒）新卒採用について、"
        f"以下を調べてください。今日は{today.isoformat()}です。\n"
        f"1. {short_year}卒の新卒採用を実施しているか、応募受付は開始/終了しているか\n"
        f"2. エントリー開始時期と応募締切\n"
        f"3. 選考フロー\n"
        f"4. インターンシップの有無と時期\n"
        f"5. 英語要件・TOEICスコア要件、帰国子女/バイリンガル向けの採用枠があるか\n"
        f"6. 初任給・待遇\n"
        f"7. 採用に関係する直近のニュース\n"
    )
    if extra_context:
        query += f"\n補足条件: {extra_context}\n"

    grounded = gemini.generate(
        query,
        system=_RESEARCH_SYSTEM,
        google_search=True,
        temperature=0,
        max_output_tokens=8192,
        thinking_level="low",
    )

    structured = gemini.generate(
        f"# 対象企業\n{company}（{grad_year}年卒）\n\n# リサーチ結果\n{grounded.text}",
        system=_STRUCTURE_SYSTEM,
        response_schema=_SCHEMA,
        temperature=0,
        max_output_tokens=4096,
        thinking_level="low",
    )

    try:
        parsed = structured.json()
    except ValueError as exc:
        raise GeminiLinkError(
            f"could not parse the structured research result for {company!r}: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise GeminiLinkError(f"expected a JSON object for {company!r}, got {type(parsed).__name__}")

    fields = {key: str(parsed.get(key) or UNKNOWN).strip() for key, _ in _LABELS}
    confidence = str(parsed.get("confidence") or "low")
    if not gemini_found_anything(fields):
        confidence = "low"

    return CompanyResearch(
        company=company,
        grad_year=grad_year,
        fields=fields,
        confidence=confidence,
        sources=grounded.sources,
        search_queries=grounded.search_queries,
        notes=grounded.text,
        researched_on=today.isoformat(),
        model=grounded.model,
    )


def gemini_found_anything(fields: dict[str, str]) -> bool:
    """True when at least one field carries something other than 不明."""
    return any(v and v != UNKNOWN for v in fields.values())


def research_many(
    companies: list[str],
    *,
    grad_year: int = 2028,
    client: GeminiClient | None = None,
    settings: Settings | None = None,
    on_error: str = "collect",
) -> tuple[list[CompanyResearch], list[tuple[str, str]]]:
    """Research several companies in sequence.

    Sequential on purpose: the free Gemini tier rate-limits aggressively, and a
    burst of parallel requests just turns into 429s.  Returns
    ``(results, failures)`` so one bad company does not lose a whole batch.
    """
    settings = settings or load_settings()
    gemini = client or GeminiClient(settings=settings)
    results: list[CompanyResearch] = []
    failures: list[tuple[str, str]] = []
    for name in companies:
        try:
            results.append(research_company(name, grad_year=grad_year, client=gemini))
        except Exception as exc:
            if on_error == "raise":
                raise
            failures.append((name, f"{type(exc).__name__}: {exc}"))
    return results, failures


def research_json(company: str, **kwargs: Any) -> str:
    return json.dumps(research_company(company, **kwargs).to_dict(), ensure_ascii=False, indent=2)
