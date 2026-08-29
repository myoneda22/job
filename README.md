# Codex × NotebookLM 連携キット

[要件定義書 v1.0](docs/01-requirements.md) を実装した、**Codex CLI / Claude Code から Google NotebookLM を直接操作するためのセットアップキット**です。

大量ドキュメント（論文・書籍・動画文字起こし）の読解を NotebookLM 側にオフロードし、
エージェント側は「オーケストレーション」と「最後の実装」だけにトークンを使う構成を作ります。

車輪の再発明はせず、既存 OSS 2 本（[notebooklm-py](https://github.com/teng-lin/notebooklm-py) /
[notebooklm-mcp](https://github.com/PleasePrompto/notebooklm-mcp)）の設定・運用・プロンプトを束ねたキットです。

---

## 5 分クイックスタート（推奨構成）

```bash
# 1. インストール（uv がなければ: curl -LsSf https://astral.sh/uv/install.sh | sh）
uv tool install "notebooklm-py[browser,mcp]"

# 2. Google ログイン（ブラウザが 1 回開きます）
notebooklm login
notebooklm auth check --test --json      # → "status": "ok" を確認

# 3. Codex CLI に MCP サーバーとして登録
codex mcp add notebooklm -- uvx --from "notebooklm-py[mcp]" notebooklm-mcp

# 4. 動作確認
notebooklm create "Test Notebook"
notebooklm ask "このノートブックのソースを要約して"
```

Windows の方は先に [`scripts/setup-windows.ps1`](scripts/setup-windows.ps1) を実行してください（文字化け対策込み）。
macOS / Linux は [`scripts/setup-unix.sh`](scripts/setup-unix.sh) が同じ手順を自動化します。

---

## ドキュメント

| # | ドキュメント | 内容 |
|---|---|---|
| 01 | [要件定義書](docs/01-requirements.md) | 元の要件 v1.0 と、FR-001〜008 のトレーサビリティ表 |
| 02 | [セットアップ手順](docs/02-setup-codex.md) | Codex CLI / Claude Code 向けの全コマンド（OS 別） |
| 03 | [ツール比較と推奨根拠](docs/03-comparison.md) | notebooklm-py vs notebooklm-mcp の比較表と選定理由 |
| 04 | [Windows 文字化け対策](docs/04-windows-encoding.md) | cp932 / UnicodeEncodeError の原因と恒久対策 |
| 05 | [プロンプトテンプレート集](docs/05-prompt-templates.md) | ユースケース別 10 本（[`prompts/`](prompts/) に個別ファイル） |
| 06 | [将来拡張案](docs/06-roadmap.md) | 横断検索・自動ソース更新・定期ブリーフィング等 |
| 07 | [トラブルシューティング](docs/07-troubleshooting.md) | 症状 → 原因 → 対処の一覧 |

## 設定ファイル雛形

| ファイル | 用途 |
|---|---|
| [`config/codex.config.toml.example`](config/codex.config.toml.example) | Codex CLI `~/.codex/config.toml` の `[mcp_servers]` ブロック |
| [`config/claude-mcp.json.example`](config/claude-mcp.json.example) | Claude Code / Cursor 向け MCP 設定 |
| [`config/env.example`](config/env.example) | 環境変数チューニング（タイムアウト・プロファイル等） |

## スクリプト

| スクリプト | 用途 |
|---|---|
| [`scripts/setup-unix.sh`](scripts/setup-unix.sh) | macOS / Linux 一括セットアップ |
| [`scripts/verify-unix.sh`](scripts/verify-unix.sh) | 導入検証（認証・CLI・MCP 登録の確認） |
| [`scripts/setup-windows.ps1`](scripts/setup-windows.ps1) | Windows 一括セットアップ（UTF-8 恒久設定込み） |
| [`scripts/fix-mojibake.ps1`](scripts/fix-mojibake.ps1) | Windows 文字化けの診断と修復 |

---

## 構成の全体像

```
Codex CLI / Claude Code
        │
        ├─ MCP (stdio)  ──►  notebooklm-py[mcp]   ──►  NotebookLM 内部 RPC API
        │                    （33 ツール）              （高速・生成物フル対応）
        │
        ├─ Bash/Skill   ──►  notebooklm CLI       ──►  同上
        │                    （ツール定義 0 個 = 最も省トークン）
        │
        └─ MCP (stdio)  ──►  notebooklm-mcp       ──►  Chrome 自動化（DOM 操作）
                             （代替構成。詳細は docs/03）
```

推奨は **notebooklm-py**（要件 FR-003 / FR-005 を単独で満たす唯一の選択肢）です。
要件定義書 6.1 は notebooklm-mcp を primary としていますが、機能充足の観点から入れ替えを提案しています。
判断根拠は [docs/03-comparison.md](docs/03-comparison.md) を参照してください。

---

## 前提条件

- Codex CLI または Claude Code
- Google アカウント（NotebookLM 利用可能なもの）
- Python 3.10+（notebooklm-py） / Node.js 18+（notebooklm-mcp を使う場合）
- 初回ログイン時のみ GUI ブラウザ（ヘッドレス運用は master-token で回避可能）

## 注意事項

- notebooklm-py / notebooklm-mcp はいずれも **非公式** ライブラリです。Google の内部 API・UI 変更で
  予告なく動かなくなる可能性があります。業務クリティカルな経路には冗長化を検討してください。
- 無料アカウントの NotebookLM には 1 日あたりのクエリ上限があります（[docs/07](docs/07-troubleshooting.md#レート制限)）。
- NotebookLM の回答は Gemini による生成物です。取り込んだ PDF 等に埋め込まれた指示文を
  エージェントの指示として扱わないでください（詳細は [docs/07](docs/07-troubleshooting.md#プロンプトインジェクション対策)）。

## ライセンス

このリポジトリの設定・ドキュメント・スクリプトは MIT。
参照している notebooklm-py / notebooklm-mcp はいずれも上流で MIT ライセンスです。
