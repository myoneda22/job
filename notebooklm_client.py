"""Claude Code から NotebookLM を叩くための CLI ラッパ。

要件定義書 v1.0 の 6.2 代替構成 (Python Skill) に対応する実装。
`notebooklm-py` (https://github.com/teng-lin/notebooklm-py) を内部で利用し、
要件定義書 6.3 で挙げられた以下のツールを CLI サブコマンドとして提供する。

- add_source       : ソース登録 (URL / ファイル)
- ask_question     : 引用付き Q&A
- list_notebooks   : ノートブック一覧
- select_notebook  : 既定ノートブックの選択 (~/.notebooklm_selected に保存)
- create_notebook  : ノートブック作成
- generate_audio   : Audio Overview (ポッドキャスト) 生成
- download_audio   : 生成済み音声のダウンロード

事前準備:
  pip install -r requirements.txt
  playwright install chromium
  notebooklm login   # Google OAuth (FR-001)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

try:
    from notebooklm import NotebookLMClient
except ImportError:
    sys.stderr.write(
        "notebooklm-py が必要です。`pip install -r requirements.txt && "
        "playwright install chromium` を実行してください。\n"
    )
    raise


SELECTED_PATH = Path.home() / ".notebooklm_selected"


def _load_selected() -> str | None:
    if SELECTED_PATH.exists():
        return SELECTED_PATH.read_text(encoding="utf-8").strip() or None
    return None


def _save_selected(notebook_id: str) -> None:
    SELECTED_PATH.write_text(notebook_id, encoding="utf-8")


def _resolve_notebook_id(explicit: str | None) -> str:
    notebook_id = explicit or _load_selected()
    if not notebook_id:
        raise SystemExit(
            "notebook_id が未指定です。--notebook で指定するか "
            "select_notebook で既定値を保存してください。"
        )
    return notebook_id


def _emit(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


async def cmd_list_notebooks(_: argparse.Namespace) -> None:
    async with await NotebookLMClient.from_storage() as client:
        notebooks = await client.notebooks.list()
        _emit([{"id": nb.id, "name": getattr(nb, "name", None)} for nb in notebooks])


async def cmd_create_notebook(args: argparse.Namespace) -> None:
    async with await NotebookLMClient.from_storage() as client:
        nb = await client.notebooks.create(args.name)
        if args.select:
            _save_selected(nb.id)
        _emit({"id": nb.id, "name": getattr(nb, "name", args.name)})


async def cmd_select_notebook(args: argparse.Namespace) -> None:
    _save_selected(args.notebook_id)
    _emit({"selected": args.notebook_id})


async def cmd_add_source(args: argparse.Namespace) -> None:
    notebook_id = _resolve_notebook_id(args.notebook)
    file_path: Path | None = None
    if args.file:
        file_path = Path(args.file).expanduser().resolve()
        if not file_path.is_file():
            raise SystemExit(f"ファイルが存在しません: {file_path}")
    async with await NotebookLMClient.from_storage() as client:
        if args.url:
            result = await client.sources.add_url(notebook_id, args.url, wait=args.wait)
        else:
            assert file_path is not None
            result = await client.sources.add_file(notebook_id, str(file_path), wait=args.wait)
        _emit({"notebook_id": notebook_id, "result": str(result)})


async def cmd_ask_question(args: argparse.Namespace) -> None:
    notebook_id = _resolve_notebook_id(args.notebook)
    async with await NotebookLMClient.from_storage() as client:
        result = await client.chat.ask(notebook_id, args.question)
        payload: dict[str, Any] = {
            "notebook_id": notebook_id,
            "question": args.question,
            "answer": getattr(result, "answer", str(result)),
        }
        citations = getattr(result, "citations", None)
        if citations is not None:
            payload["citations"] = citations
        _emit(payload)


async def cmd_generate_audio(args: argparse.Namespace) -> None:
    notebook_id = _resolve_notebook_id(args.notebook)
    async with await NotebookLMClient.from_storage() as client:
        task = await client.artifacts.generate_audio(notebook_id, args.instructions)
        if args.wait:
            await client.artifacts.wait_for_completion(notebook_id, task.id)
        _emit({"notebook_id": notebook_id, "task_id": getattr(task, "id", None)})


async def cmd_download_audio(args: argparse.Namespace) -> None:
    notebook_id = _resolve_notebook_id(args.notebook)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    async with await NotebookLMClient.from_storage() as client:
        await client.artifacts.download_audio(notebook_id, str(output))
    _emit({"notebook_id": notebook_id, "saved_to": str(output)})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Claude Code 用 NotebookLM ブリッジ")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list_notebooks", help="ノートブック一覧").set_defaults(
        func=cmd_list_notebooks
    )

    p_create = sub.add_parser("create_notebook", help="ノートブック作成")
    p_create.add_argument("name")
    p_create.add_argument(
        "--select", action="store_true", help="作成後に既定ノートブックとして保存"
    )
    p_create.set_defaults(func=cmd_create_notebook)

    p_select = sub.add_parser("select_notebook", help="既定ノートブックを保存")
    p_select.add_argument("notebook_id")
    p_select.set_defaults(func=cmd_select_notebook)

    p_add = sub.add_parser("add_source", help="ソース登録")
    p_add.add_argument("--notebook")
    src = p_add.add_mutually_exclusive_group(required=True)
    src.add_argument("--url")
    src.add_argument("--file")
    p_add.add_argument(
        "--no-wait",
        dest="wait",
        action="store_false",
        help="取り込み完了を待たない",
    )
    p_add.set_defaults(wait=True, func=cmd_add_source)

    p_ask = sub.add_parser("ask_question", help="引用付き Q&A")
    p_ask.add_argument("question")
    p_ask.add_argument("--notebook")
    p_ask.set_defaults(func=cmd_ask_question)

    p_gen = sub.add_parser("generate_audio", help="Audio Overview 生成")
    p_gen.add_argument("--notebook")
    p_gen.add_argument("--instructions", default="")
    p_gen.add_argument(
        "--wait", action="store_true", help="生成完了までポーリングして待機"
    )
    p_gen.set_defaults(func=cmd_generate_audio)

    p_dl = sub.add_parser("download_audio", help="音声ダウンロード")
    p_dl.add_argument("--notebook")
    p_dl.add_argument("--output", default="podcast.mp3")
    p_dl.set_defaults(func=cmd_download_audio)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    asyncio.run(args.func(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
