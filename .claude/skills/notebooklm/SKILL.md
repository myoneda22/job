---
name: notebooklm
description: Bridge Claude Code to Google NotebookLM via the notebooklm-py Python skill. Use when the user asks to register sources (URL/PDF/text/Drive), ask cited questions, list/create/select notebooks, or generate/download Audio Overview podcasts on NotebookLM.
---

# NotebookLM Skill

Claude Code から `notebooklm_client.py` 経由で NotebookLM を操作する。

## Prerequisites (一度だけ)

```bash
pip install -r requirements.txt
playwright install chromium
notebooklm login          # Google OAuth
```

## Commands

すべて `python notebooklm_client.py <subcommand>` で実行する。出力は JSON。

| 用途 | コマンド |
| --- | --- |
| ノートブック一覧 | `python notebooklm_client.py list_notebooks` |
| ノートブック作成 | `python notebooklm_client.py create_notebook "Research" --select` |
| 既定ノートブック選択 | `python notebooklm_client.py select_notebook <notebook_id>` |
| URL ソース追加 | `python notebooklm_client.py add_source --url https://example.com` |
| ファイルソース追加 | `python notebooklm_client.py add_source --file ./paper.pdf` |
| 引用付き Q&A | `python notebooklm_client.py ask_question "主要な貢献を比較して"` |
| 音声 (Audio Overview) 生成 | `python notebooklm_client.py generate_audio --wait` |
| 音声ダウンロード | `python notebooklm_client.py download_audio --output ./podcast.mp3` |

`--notebook <id>` を渡さない場合、`select_notebook` で保存した既定値 (`~/.notebooklm_selected`) が使われる。

## Workflow

1. `list_notebooks` で既存を確認 (なければ `create_notebook ... --select`)。
2. `add_source` を必要数だけ繰り返す。複数ソースは並列ではなく順次実行する (NotebookLM 側のレート制限回避)。
3. `ask_question` で引用付き回答を取得。
4. 必要なら `generate_audio --wait` → `download_audio` でポッドキャスト化。

## Notes

- 認証エラーが出たら `notebooklm login` を再実行する (FR-008)。
- Windows で日本語が文字化けする場合は `PYTHONUTF8=1` を設定する。
- すべての回答は NotebookLM 側で引用が付与される。引用無しの回答が返ってきた場合は信頼せず再質問する。
