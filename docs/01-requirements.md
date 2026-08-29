# Codex × NotebookLM 連携システム 要件定義書 v1.0

> 元文書: `Codex × NotebookLM 連携システム 要件定義書` Version 1.0 / 2026年5月5日
> 本ファイルは元 PDF の内容を転記し、末尾に **実装トレーサビリティ** を追記したものです。

---

## 1. ドキュメント情報

- **作成目的**: X（旧 Twitter）上の実践事例調査を基に、Codex と NotebookLM の連携システムに関する正式な要件を定義。Claude（Claude Code / Cursor 等）にそのまま投入して、セットアップガイド・実装支援・カスタマイズを効率的に行うためのベースドキュメントとする。
- **対象読者**: Claude Code / Codex ユーザー、AI 駆動開発者
- **参照ソース**: X 投稿（2026 年 4〜5 月）、GitHub リポジトリ (notebooklm-mcp, notebooklm-py)

## 2. 目的

AI コーディングエージェント「Codex」から Google NotebookLM のノートブックに対して直接連携を実現し、以下の価値を提供する:

- 大量ドキュメント（論文・書籍・動画文字起こし等）の分析を NotebookLM にオフロード
- Codex 側のトークン消費を 70% 以上削減
- ソース引用付きの根拠ある回答を取得（ハルシネーション低減）
- 研究 → 実装のシームレスなワークフローを構築

## 3. 背景と課題

### 3.1 現在の状況（X 調査結果）

2026 年 4〜5 月、X 日本語圏で「Codex + NotebookLM」連携が急速に拡大。主なツールとして notebooklm-py（Python Skill）と notebooklm-mcp（MCP サーバー）が実践されている。

- ユーザーの声: 「本一冊を Codex に喰わせるのは無理だが、NotebookLM 経由なら可能になった」
- 「YouTube 文字起こしを NotebookLM に任せて、結果を Claude Code/Codex で取得 → トークン劇的に抑えられる」
- 「notebooklm-py は無茶いい。Codex に丸投げで完璧に動いた」

### 3.2 解決すべき課題

- Codex 単体ではコンテキスト長・コストの制限が厳しい
- 手動で NotebookLM の結果をコピー＆ペーストするのは非効率
- Windows 環境での文字化けなどの実装障壁

## 4. 機能要件 (Functional Requirements)

| ID | 要件名 | 詳細説明 | 優先度 |
|---|---|---|---|
| FR-001 | NotebookLM 接続 | MCP サーバーまたは Python Skill 経由で Google 認証・セッション確立 | 高 |
| FR-002 | ノートブック管理 | ノートブックの一覧表示・作成・選択・削除・切り替え | 高 |
| FR-003 | ソース追加 | URL / PDF / YouTube / テキスト / Google Drive の一括登録 | 高 |
| FR-004 | 質問実行 | 自然言語クエリに対し、ソース引用付き回答を返す (ask_question ツール) | 高 |
| FR-005 | コンテンツ生成 | Audio Overview（ポッドキャスト）、Mind Map、Study Guide、FAQ、Quiz の生成・エクスポート | 中 |
| FR-006 | Codex 統合 | Codex CLI から MCP/Skill としてツール呼び出し可能 (codex mcp add) | 高 |
| FR-007 | 永続セッション | 複数ノートブックの同時管理とセッション永続化 | 中 |
| FR-008 | エラーハンドリング | Windows 文字化け対策、認証エラー時の再認証フロー | 高 |

## 5. 非機能要件 (Non-Functional Requirements)

- **トークン効率**: Codex 単体比で 70% 以上削減（NotebookLM オフロードによる）
- **回答品質**: すべての回答にソース引用 (citation) を必須とする
- **対応環境**: Windows 10/11, macOS, Linux (Ubuntu 推奨)
- **セキュリティ**: Google OAuth の安全な扱い、ブラウザフィンガープリント保護 (MCP の場合)
- **メンテナンス性**: 既存 OSS (notebooklm-mcp / notebooklm-py) を最大限活用し、車輪の再発明を避ける

## 6. システム構成・技術スタック

### 6.1 推奨構成 (Primary) ※元文書

`Codex CLI → notebooklm-mcp (MCP サーバー) → NotebookLM (ブラウザ自動化)`

インストール: `codex mcp add notebooklm npx notebooklm-mcp@latest`

> **本キットでの変更点**: FR-003 / FR-005 の充足範囲を根拠に、primary を **notebooklm-py** に入れ替えることを提案しています。判断根拠は [03-comparison.md](03-comparison.md) を参照。

### 6.2 代替構成 (Python Skill)

`Codex / Claude Code → notebooklm-py (Python Skill) → NotebookLM`
GitHub: https://github.com/teng-lin/notebooklm-py

### 6.3 主なツール一覧

- `ask_question` — 引用付き Q&A
- `add_source` — ソース登録
- `generate_audio` / `download_audio` — ポッドキャスト生成
- `list_notebooks` / `select_notebook` — ノートブック管理

## 7. ユースケース (Use Cases)

| ID | 名称 | 内容 |
|---|---|---|
| UC1 | 研究論文比較 | 10 本の論文を NotebookLM に登録 → Codex から「主要なコントリビューションの違いを比較せよ」と質問 → 引用付きで回答 |
| UC2 | 動画→コード実装 | 技術系 YouTube 動画を NotebookLM で文字起こし＋分析 → Codex で実装コードを自動生成 |
| UC3 | 書籍丸ごと活用 | 技術書 1 冊を NotebookLM に投入 → Codex から「第 3 章のアルゴリズムを Python で実装せよ」と指示 |
| UC4 | クオンツ研究 | 最新論文を NotebookLM で理解 → Codex にトレード戦略のコード化を依頼 |

## 8. 導入・運用要件

### 8.1 前提条件

- Codex CLI または Claude Code が利用可能
- Google アカウント（NotebookLM 利用権限あり）
- Node.js 18+ または Python 3.10+
- Playwright / Chromium (MCP 利用時)

### 8.2 文字化け対策 (Windows 特有)

X 実践者報告より、notebooklm-py 使用時に Windows で文字化けが発生するケースあり。Codex に「Windows 文字化け対策を適用せよ」と指示して自動修正可能。

> 恒久対策の詳細は [04-windows-encoding.md](04-windows-encoding.md) を参照。

## 9. 参考情報

### 9.1 GitHub リポジトリ

- notebooklm-mcp: https://github.com/PleasePrompto/notebooklm-mcp
- notebooklm-py: https://github.com/teng-lin/notebooklm-py

### 9.2 X 投稿例 (2026 年 4-5 月)

- @tetumemo: 「Claude Code や Codex と NotebookLM を接続させるためのリポジトリ notebooklm-py」
- @makodama: 「Codex に notebooklm-py を導入。トークン省略のための MCP サーバーも一緒に」

## 10. Claude への指示（このドキュメントの使い方）

上記の要件定義書を完全に理解した上で、以下のタスクを実行してください:

1. Codex CLI で即座に利用可能な詳細セットアップ手順（コマンド全文）を生成
2. notebooklm-mcp と notebooklm-py の比較表と、どちらを推奨するかの判断根拠
3. Windows 文字化け完全対策スクリプト
4. 実際のユースケースに即した Codex 用プロンプトテンプレート集（5〜10 個）
5. 将来的な拡張案（複数ノートブック横断検索、自動ソース更新など）

---

# 実装トレーサビリティ

§10 の 5 タスクと、本キットの成果物の対応:

| §10 タスク | 成果物 |
|---|---|
| 1. 詳細セットアップ手順 | [02-setup-codex.md](02-setup-codex.md), [`scripts/`](../scripts/), [`config/`](../config/) |
| 2. 比較表と推奨根拠 | [03-comparison.md](03-comparison.md) |
| 3. Windows 文字化け完全対策 | [04-windows-encoding.md](04-windows-encoding.md), [`scripts/fix-mojibake.ps1`](../scripts/fix-mojibake.ps1) |
| 4. プロンプトテンプレート集 | [05-prompt-templates.md](05-prompt-templates.md), [`prompts/`](../prompts/) |
| 5. 将来拡張案 | [06-roadmap.md](06-roadmap.md) |

## 機能要件 (FR) の充足状況

「py」= notebooklm-py、「mcp」= notebooklm-mcp。上流 README / docs の記載に基づく（2026-08 時点）。

| ID | py | mcp | 実現手段 | 備考 |
|---|:--:|:--:|---|---|
| FR-001 NotebookLM 接続 | ✅ | ✅ | py: `notebooklm login`（対話 / ブラウザ Cookie 取込 / master-token）<br>mcp: `setup_auth` ツール | py は master-token により完全無人での再認証が可能 |
| FR-002 ノートブック管理 | ✅ | ⚠️ | py: `create` / `list` / `use` / rename / delete<br>mcp: `add_notebook` / `list_notebooks` / `select_notebook` / `remove_notebook` | mcp の library は**ローカル台帳**。`remove_notebook` は NotebookLM 側のノートを削除しない |
| FR-003 ソース追加 | ✅ | ⚠️ | py: URL / YouTube / ローカルファイル（PDF, Word, EPUB, 音声, 動画, 画像）/ Google Drive / 貼り付けテキスト<br>mcp: `add_source` は `type=url` と `type=text` のみ | **PDF / YouTube / Drive の登録は py のみ**。mcp では要件未達 |
| FR-004 質問実行 | ✅ | ✅ | py: `notebooklm ask` / `ask --json`<br>mcp: `ask_question`（`source_format=none/inline/footnotes/json`） | 引用取得はどちらも可。mcp は DOM から引用パネルを抽出 |
| FR-005 コンテンツ生成 | ✅ | ⚠️ | py: audio / video / slide-deck / infographic / quiz / flashcards / report(briefing-doc, study-guide, blog) / data-table / mind-map<br>mcp: `generate_audio` / `download_audio` のみ | **Mind Map / Study Guide / Quiz は py のみ**。mcp では要件未達 |
| FR-006 Codex 統合 | ✅ | ✅ | 両者とも `codex mcp add` で stdio MCP として登録可。py は CLI 直叩き（Skill / AGENTS.md）も可能 | [02-setup-codex.md](02-setup-codex.md) 参照 |
| FR-007 永続セッション | ✅ | ✅ | py: プロファイル（`~/.notebooklm/profiles/<name>/`）で複数アカウント / 並行エージェントを分離<br>mcp: `list_sessions` / `close_session` / `reset_session` + 永続 Chrome プロファイル | 「複数ノートブックの同時管理」は py なら `--notebook` 明示指定で自然に実現 |
| FR-008 エラーハンドリング | ✅ | ✅ | py: CLI 起動時に `PYTHONUTF8=1` を自動設定、`auth check --test` / `auth refresh`<br>mcp: `get_health` / `re_auth` / `cleanup_data` | Windows 文字化けは [04](04-windows-encoding.md) で恒久対策 |

**結論**: 高優先度の FR-003 と中優先度の FR-005 を単独で満たすのは notebooklm-py のみ。
notebooklm-mcp を primary にすると FR-003 / FR-005 が要件未達になるため、本キットでは primary を入れ替えている。

## 非機能要件 (NFR) の扱い

| NFR | 本キットでの対応 |
|---|---|
| トークン効率 70% 削減 | 削減率は「元のドキュメント量 ÷ 回答量」に依存するため保証はできない。実測手順と削減幅を稼ぐ設定（MCP ツール絞り込み / CLI 経由）を [03-comparison.md](03-comparison.md#トークン効率の実際) に記載 |
| 回答品質（引用必須） | py は `ask --json`、mcp は `source_format=footnotes` を既定として推奨。プロンプトテンプレートにも引用指示を組み込み済み |
| 対応環境 | Windows 10/11・macOS・Linux 向けにセットアップスクリプトを用意。既知の OS 別問題は [07](07-troubleshooting.md) に集約 |
| セキュリティ | 認証情報の保存先と取り扱い、非公開 API 利用のリスク、プロンプトインジェクション対策を [07](07-troubleshooting.md) に明記 |
| メンテナンス性 | 独自ラッパーを実装せず、設定・スクリプト・ドキュメントのみを提供。上流の破壊的変更の影響を最小化 |
