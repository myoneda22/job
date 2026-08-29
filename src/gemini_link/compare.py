"""Ask Claude and Gemini the same question and cross-check the two answers.

The point is not to pick a winner but to surface disagreement: when both models
independently say the same thing the claim is probably safe to act on, and when
they diverge that is exactly the spot a human should look at.  Used for
fact-checking job-hunting information, where a confidently wrong application
deadline is expensive.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any

from .claude import ClaudeClient
from .config import Settings, load_settings
from .gemini import GeminiClient, Source

# Asked of the judge model.  It only ever sees the two answers, never which
# model produced which, so the verdict cannot be biased toward a vendor.
_JUDGE_SYSTEM = """\
You compare two independent answers to the same question and report where they
agree and where they disagree. Judge only the substance — factual claims, dates,
numbers, names, and conclusions. Ignore differences in wording, length, tone and
formatting.

Reply with JSON only, matching this shape:
{
  "verdict": "agree" | "partial" | "conflict",
  "agreements": ["<claim both answers make>"],
  "conflicts": [
    {"topic": "<what they disagree about>", "answer_a": "<A's claim>", "answer_b": "<B's claim>"}
  ],
  "unverified": ["<claim only one answer makes, unconfirmed by the other>"],
  "summary": "<two sentences a reader can act on>"
}
Use "conflict" only when the two answers cannot both be true."""

_JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["agree", "partial", "conflict"]},
        "agreements": {"type": "array", "items": {"type": "string"}},
        "conflicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "answer_a": {"type": "string"},
                    "answer_b": {"type": "string"},
                },
                "required": ["topic", "answer_a", "answer_b"],
            },
        },
        "unverified": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["verdict", "summary"],
}


@dataclass
class AnswerResult:
    """One model's answer, or the reason it could not produce one."""

    provider: str
    model: str
    text: str = ""
    sources: list[Source] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.text)


@dataclass
class Comparison:
    question: str
    gemini: AnswerResult
    claude: AnswerResult
    verdict: str
    summary: str
    agreements: list[str] = field(default_factory=list)
    conflicts: list[dict[str, str]] = field(default_factory=list)
    unverified: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for side in ("gemini", "claude"):
            data[side]["sources"] = [asdict(s) for s in getattr(self, side).sources]
        return data

    def to_text(self) -> str:
        """Human-readable report, conflicts first because that is the payload."""
        icon = {"agree": "✅", "partial": "⚠️", "conflict": "❌"}.get(self.verdict, "•")
        lines = [f"{icon} 判定: {self.verdict}", "", f"要約: {self.summary}", ""]
        if self.conflicts:
            lines.append("── 不一致（要確認） ──")
            for c in self.conflicts:
                lines.append(f"  • {c.get('topic', '')}")
                lines.append(f"      Gemini: {c.get('answer_a', '')}")
                lines.append(f"      Claude: {c.get('answer_b', '')}")
            lines.append("")
        if self.agreements:
            lines.append("── 両モデル一致 ──")
            lines += [f"  • {a}" for a in self.agreements]
            lines.append("")
        if self.unverified:
            lines.append("── 片方のみの主張（裏取り未了） ──")
            lines += [f"  • {u}" for u in self.unverified]
            lines.append("")
        for result in (self.gemini, self.claude):
            head = f"── {result.provider} ({result.model}) ──"
            lines.append(head)
            lines.append(result.text if result.ok else f"  [失敗] {result.error}")
            if result.sources:
                lines.append("  出典:")
                lines += [f"    - {s.title}: {s.uri}" for s in result.sources]
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


def compare(
    question: str,
    *,
    settings: Settings | None = None,
    gemini_client: GeminiClient | None = None,
    claude_client: ClaudeClient | None = None,
    system: str | None = None,
    google_search: bool = False,
    max_output_tokens: int = 4096,
) -> Comparison:
    """Ask both providers, then judge the pair.

    Degrades rather than fails: if ``ANTHROPIC_API_KEY`` is missing, or either
    call errors, the surviving answer is still returned with the verdict saying
    plainly that no cross-check happened.
    """
    settings = settings or load_settings()
    gemini = gemini_client or GeminiClient(settings=settings)

    claude: ClaudeClient | None = claude_client
    claude_error: str | None = None
    if claude is None:
        if settings.has_anthropic:
            claude = ClaudeClient(settings=settings)
        else:
            claude_error = "ANTHROPIC_API_KEY 未設定のため Claude 側は実行していません"

    def ask_gemini() -> AnswerResult:
        try:
            resp = gemini.generate(
                question,
                system=system,
                google_search=google_search,
                max_output_tokens=max_output_tokens,
            )
            return AnswerResult("Gemini", resp.model, resp.text, resp.sources)
        except Exception as exc:
            return AnswerResult("Gemini", gemini.model, error=f"{type(exc).__name__}: {exc}")

    def ask_claude() -> AnswerResult:
        if claude is None:
            return AnswerResult("Claude", settings.anthropic_model, error=claude_error)
        try:
            text = claude.generate(question, system=system, max_tokens=max_output_tokens)
            return AnswerResult("Claude", claude.model, text)
        except Exception as exc:
            return AnswerResult("Claude", claude.model, error=f"{type(exc).__name__}: {exc}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        g_future = pool.submit(ask_gemini)
        c_future = pool.submit(ask_claude)
        g_result, c_result = g_future.result(), c_future.result()

    if not (g_result.ok and c_result.ok):
        missing = c_result.error if g_result.ok else g_result.error
        return Comparison(
            question=question,
            gemini=g_result,
            claude=c_result,
            verdict="single",
            summary=f"片側のみの回答のため相互検証できていません: {missing}",
        )

    return _judge(question, g_result, c_result, gemini)


def _judge(
    question: str, a: AnswerResult, b: AnswerResult, gemini: GeminiClient
) -> Comparison:
    prompt = (
        f"# 質問\n{question}\n\n"
        f"# 回答A\n{a.text}\n\n"
        f"# 回答B\n{b.text}\n"
    )
    try:
        resp = gemini.generate(
            prompt,
            system=_JUDGE_SYSTEM,
            response_schema=_JUDGE_SCHEMA,
            temperature=0,
            max_output_tokens=4096,
            thinking_level="low",
        )
        data = resp.json()
    except Exception as exc:
        return Comparison(
            question=question,
            gemini=a,
            claude=b,
            verdict="unjudged",
            summary=f"両モデルの回答は得られましたが、突き合わせ判定に失敗しました: "
                    f"{type(exc).__name__}: {exc}",
        )
    if not isinstance(data, dict):
        data = {}
    return Comparison(
        question=question,
        gemini=a,
        claude=b,
        verdict=str(data.get("verdict", "unjudged")),
        summary=str(data.get("summary", "")),
        agreements=[str(x) for x in data.get("agreements", []) or []],
        conflicts=[x for x in data.get("conflicts", []) or [] if isinstance(x, dict)],
        unverified=[str(x) for x in data.get("unverified", []) or []],
    )


def compare_json(question: str, **kwargs: Any) -> str:
    return json.dumps(compare(question, **kwargs).to_dict(), ensure_ascii=False, indent=2)
