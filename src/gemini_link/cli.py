"""Command line entry point: ``python -m gemini_link.cli <command>``.

Commands:
  ask      one-shot generation
  search   Google-grounded answer with sources
  compare  ask Claude and Gemini the same thing and cross-check them
  company  research a company's new-grad hiring, print the 備考 text
  batch    the same for a list of companies from a file
  models   list the models this key can reach
  status   show the current configuration (keys redacted)
"""

from __future__ import annotations

import argparse
import json
import sys

from .compare import compare
from .config import load_settings
from .errors import ConfigError, GeminiLinkError
from .gemini import GeminiClient
from .shukatsu import research_company, research_company_from_urls, research_many


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", help="override the Gemini model for this call")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gemini-link", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    ask = sub.add_parser("ask", help="one-shot generation")
    ask.add_argument("prompt", nargs="+")
    ask.add_argument("--system")
    ask.add_argument("--temperature", type=float)
    ask.add_argument("--max-tokens", type=int, default=4096)
    ask.add_argument("--stream", action="store_true", help="stream the answer as it arrives")
    _add_common(ask)

    search = sub.add_parser("search", help="Google-grounded answer with sources")
    search.add_argument("query", nargs="+")
    _add_common(search)

    cmp_ = sub.add_parser("compare", help="cross-check Claude against Gemini")
    cmp_.add_argument("question", nargs="+")
    cmp_.add_argument("--search", action="store_true", help="let Gemini ground its answer")
    _add_common(cmp_)

    company = sub.add_parser("company", help="research one company's new-grad hiring")
    company.add_argument("company")
    company.add_argument("--grad-year", type=int, default=2028)
    company.add_argument(
        "--url",
        action="append",
        dest="urls",
        help="read this page instead of searching (repeatable). Use when the "
             "search-grounding quota is exhausted.",
    )
    _add_common(company)

    read = sub.add_parser("read-urls", help="answer from specific pages only")
    read.add_argument("question")
    read.add_argument("--url", action="append", dest="urls", required=True,
                      help="page to read (repeatable)")
    _add_common(read)

    batch = sub.add_parser("batch", help="research many companies (one name per line)")
    batch.add_argument("file", help="path to a newline-separated list, or - for stdin")
    batch.add_argument("--grad-year", type=int, default=2028)
    _add_common(batch)

    sub.add_parser("models", help="list reachable Gemini models")
    sub.add_parser("status", help="show configuration (keys redacted)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _dispatch(args)
    except ConfigError as exc:
        print(f"設定エラー: {exc}", file=sys.stderr)
        return 2
    except GeminiLinkError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover
        return 130


def _dispatch(args: argparse.Namespace) -> int:
    settings = load_settings()

    if args.command == "status":
        print(settings.describe())
        return 0

    model = getattr(args, "model", None)
    client = GeminiClient(settings=settings, model=model)

    if args.command == "models":
        for m in client.list_models():
            if "generateContent" not in m.get("supportedGenerationMethods", []):
                continue
            name = m.get("name", "").replace("models/", "")
            print(f"{name:42s} in={m.get('inputTokenLimit')} out={m.get('outputTokenLimit')}")
        return 0

    if args.command == "ask":
        prompt = " ".join(args.prompt)
        if args.stream:
            for chunk in client.stream(
                prompt,
                system=args.system,
                temperature=args.temperature,
                max_output_tokens=args.max_tokens,
            ):
                sys.stdout.write(chunk)
                sys.stdout.flush()
            print()
            return 0
        resp = client.generate(
            prompt,
            system=args.system,
            temperature=args.temperature,
            max_output_tokens=args.max_tokens,
        )
        print(json.dumps({"model": resp.model, "text": resp.text, "usage": resp.usage},
                         ensure_ascii=False, indent=2) if args.json else resp.text)
        return 0

    if args.command == "search":
        resp = client.generate(
            " ".join(args.query),
            google_search=True,
            temperature=0,
            max_output_tokens=8192,
            thinking_level="low",
        )
        if args.json:
            print(json.dumps(
                {"text": resp.text,
                 "queries": resp.search_queries,
                 "sources": [{"title": s.title, "uri": s.uri} for s in resp.sources]},
                ensure_ascii=False, indent=2))
        else:
            print(resp.text)
            if resp.sources:
                print("\n── 出典 ──")
                for s in resp.sources:
                    print(f"- {s.title}: {s.uri}")
        return 0

    if args.command == "compare":
        result = compare(
            " ".join(args.question),
            settings=settings,
            gemini_client=client,
            google_search=args.search,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
              if args.json else result.to_text())
        return 0 if result.verdict in ("agree", "partial") else 1

    if args.command == "read-urls":
        resp = client.generate(
            "\n".join(args.urls) + "\n\n" + args.question,
            system=(
                "指定されたURLのページを実際に読み、そこに書かれている内容だけを使って答えてください。"
                "ページを取得できなかった場合、記憶や一般知識で補ってはいけません。"
            ),
            url_context=True,
            temperature=0,
            max_output_tokens=8192,
            thinking_level="low",
        )
        failures = resp.retrieval_failures
        if args.json:
            print(json.dumps(
                {"text": resp.text,
                 "grounded": not failures and bool(resp.retrieved_urls),
                 "retrieved": [{"url": u.url, "status": u.status, "ok": u.ok}
                               for u in resp.retrieved_urls]},
                ensure_ascii=False, indent=2))
        else:
            if failures:
                print("警告: 以下のページを取得できませんでした。"
                      "この回答は記憶で補われている可能性があり、信頼できません。", file=sys.stderr)
                for u in failures:
                    print(f"  - {u.url} ({u.status})", file=sys.stderr)
            print(resp.text)
            if resp.retrieved_urls and not failures:
                print("\n── 実際に読んだページ ──")
                for u in resp.retrieved_urls:
                    print(f"- {u.url}")
        return 1 if failures or not resp.retrieved_urls else 0

    if args.command == "company":
        if getattr(args, "urls", None):
            result = research_company_from_urls(
                args.company, args.urls, grad_year=args.grad_year, client=client
            )
        else:
            result = research_company(args.company, grad_year=args.grad_year, client=client)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
              if args.json else result.to_remarks())
        return 0

    if args.command == "batch":
        raw = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
        names = [line.strip() for line in raw.splitlines() if line.strip()]
        results, failures = research_many(names, grad_year=args.grad_year, client=client)
        if args.json:
            print(json.dumps(
                {"results": [r.to_dict() for r in results],
                 "failures": [{"company": c, "error": e} for c, e in failures]},
                ensure_ascii=False, indent=2))
        else:
            for r in results:
                print(f"===== {r.company} =====")
                print(r.to_remarks())
                print()
            for name, err in failures:
                print(f"[失敗] {name}: {err}", file=sys.stderr)
        return 1 if failures else 0

    raise AssertionError(f"unhandled command {args.command!r}")  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
