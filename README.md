# job

Claude Code × NotebookLM 連携リポジトリ。要件定義書 v1.0 の **6.2 代替構成 (Python Skill)** に基づき、`notebooklm-py` を Claude Code から呼び出すための薄いラッパーと skill を提供する。

```
Claude Code → notebooklm_client.py → notebooklm-py → NotebookLM (browser auto)
```

## セットアップ

```bash
pip install -r requirements.txt
playwright install chromium
notebooklm login           # Google OAuth (FR-001)
```

## 使い方 (CLI)

```bash
# ノートブック一覧 / 作成 / 既定選択
python notebooklm_client.py list_notebooks
python notebooklm_client.py create_notebook "Research" --select
python notebooklm_client.py select_notebook <notebook_id>

# ソース追加 (URL / ファイル) - FR-003
python notebooklm_client.py add_source --url https://example.com/paper.pdf
python notebooklm_client.py add_source --file ./paper.pdf

# 引用付き Q&A - FR-004
python notebooklm_client.py ask_question "主要なコントリビューションの違いを比較せよ"

# Audio Overview 生成 / ダウンロード - FR-005
python notebooklm_client.py generate_audio --wait
python notebooklm_client.py download_audio --output ./podcast.mp3
```

`--notebook <id>` を省略すると、`select_notebook` で保存した既定値 (`~/.notebooklm_selected`) が使われる。

## Claude Code から使う

`.claude/skills/notebooklm/SKILL.md` に skill 定義があるため、Claude Code セッションで「NotebookLM にソース追加して」「○○について質問して」等の自然言語指示で自動的に上記 CLI を叩く。

## 対応要件

| ID | 要件 | 実装 |
| --- | --- | --- |
| FR-001 | NotebookLM 接続 | `notebooklm login` (Google OAuth) |
| FR-002 | ノートブック管理 | `list_notebooks` / `create_notebook` / `select_notebook` |
| FR-003 | ソース追加 | `add_source --url` / `add_source --file` |
| FR-004 | 引用付き Q&A | `ask_question` |
| FR-005 | コンテンツ生成 | `generate_audio` / `download_audio` |
| FR-006 | Claude Code 統合 | `.claude/skills/notebooklm/` |
| FR-008 | エラーハンドリング | 認証エラー時に `notebooklm login` 再実行を案内 |
