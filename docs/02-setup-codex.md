# セットアップ手順（Codex CLI / Claude Code）

要件定義書 §10-1「Codex CLI で即座に利用可能な詳細セットアップ手順（コマンド全文）」に対応。

対象: **推奨構成 = notebooklm-py**。代替構成の notebooklm-mcp は [§5](#5-代替構成-notebooklm-mcp) にまとめています。
選定理由は [03-comparison.md](03-comparison.md) を参照。

- [0. 事前確認](#0-事前確認)
- [1. インストール](#1-インストール)
- [2. Google 認証](#2-google-認証)
- [3. Codex CLI への登録](#3-codex-cli-への登録)
- [4. Claude Code / Cursor への登録](#4-claude-code--cursor-への登録)
- [5. 代替構成: notebooklm-mcp](#5-代替構成-notebooklm-mcp)
- [6. 動作確認](#6-動作確認)
- [7. ヘッドレス / サーバー運用](#7-ヘッドレス--サーバー運用)

---

## 0. 事前確認

```bash
python3 --version     # 3.10 〜 3.14
codex --version       # Codex CLI（Claude Code の場合は claude --version）
node --version        # 18+（notebooklm-mcp を使う場合のみ必須）
```

`uv` が未導入なら先に入れます（`uv tool` はコマンドを隔離環境に入れて PATH に通すため、
Homebrew Python や Debian/Ubuntu の `externally-managed-environment` エラーを回避できます）。

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
# macOS (Homebrew)
brew install uv
# Windows
winget install astral-sh.uv
```

---

## 1. インストール

### macOS / Linux

```bash
uv tool install "notebooklm-py[browser,mcp]"
```

- `browser` … Playwright + Chromium（対話ログインに必要）
- `mcp` … MCP サーバーアダプタ（`fastmcp`）。CLI/Skill だけで使う場合は不要

`pipx` 派、あるいは venv 内の `pip` でも同じです。

```bash
pipx install "notebooklm-py[browser,mcp]"
# または
python3 -m venv .venv && source .venv/bin/activate
pip install "notebooklm-py[browser,mcp]"
```

### Windows (PowerShell)

文字化け対策を含む一括セットアップは [`scripts/setup-windows.ps1`](../scripts/setup-windows.ps1) を使ってください。

```powershell
# 恒久 UTF-8 設定（詳細は docs/04）
[Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'User')
$env:PYTHONUTF8 = '1'

winget install astral-sh.uv
uv tool install "notebooklm-py[browser,mcp]"
```

### 自動化・CI 用の追加 extra

```bash
uv tool install "notebooklm-py[browser,mcp,headless,cookies]"
```

- `headless` … master-token 認証（無人運用の要）
- `cookies` … 既にログイン済みブラウザから Cookie を取り込む `--browser-cookies`

---

## 2. Google 認証

### 標準（GUI がある環境）

```bash
notebooklm login                      # ブラウザが開くので Google にサインイン
notebooklm auth check --test --json   # → "status": "ok"
```

初回は Chromium（約 170 MB）が自動ダウンロードされます。

### 会社 SSO が Edge 必須の場合

```bash
notebooklm login --browser msedge
```

### 既存ブラウザの Cookie を取り込む（Playwright 不要）

```bash
notebooklm login --browser-cookies firefox
```

> **Windows で `--browser-cookies chrome` は使えません。** Chrome 127+ / 現行 Edge は
> App-Bound Encryption でクッキー DB を保護しており、外部プロセスから復号できません。
> Windows では **Firefox** を Cookie ソースにするか、master-token を使ってください。
> 詳細: [07-troubleshooting.md](07-troubleshooting.md#windows-認証が通らない)

### 無人運用（master-token）

```bash
notebooklm login --master-token --account you@example.com
```

以降は保存された `master_token.json` から Cookie を都度再発行するため、
セッション切れを自動で自己修復します。サーバー / CI / リモート MCP はこの方式が前提です。

### 認証情報の保存場所

| 対象 | パス |
|---|---|
| notebooklm-py プロファイル | `~/.notebooklm/profiles/<name>/` |
| notebooklm-mcp Chrome プロファイル (Linux) | `~/.local/share/notebooklm-mcp/chrome_profile/` |
| notebooklm-mcp Chrome プロファイル (macOS) | `~/Library/Application Support/notebooklm-mcp/chrome_profile/` |
| notebooklm-mcp Chrome プロファイル (Windows) | `%APPDATA%\notebooklm-mcp\chrome_profile\` |

いずれも **Google のセッションクッキーそのもの** が入ります。リポジトリにコミットしない、
バックアップから除外する、共有マシンでは使わない、を徹底してください。

---

## 3. Codex CLI への登録

Codex には **2 つの繋ぎ方** があります。用途で選んでください。

### 3-A. MCP サーバーとして登録（対話利用向け）

```bash
codex mcp add notebooklm -- uvx --from "notebooklm-py[mcp]" notebooklm-mcp
codex mcp list
```

`uv tool install` 済みなら `notebooklm-mcp` を直接指定しても構いません。

```bash
codex mcp add notebooklm -- notebooklm-mcp
```

プロファイルを固定する場合:

```bash
codex mcp add notebooklm -- notebooklm-mcp --profile work
```

> **名前の衝突に注意。** `notebooklm-py[mcp]` が入れるコンソールスクリプトは
> `notebooklm-mcp` という名前で、npm パッケージ `notebooklm-mcp` のバイナリと同名です。
> 両方入れる場合はどちらが PATH 上で優先されるか（`which notebooklm-mcp`）を必ず確認し、
> Codex 側では `uvx --from ...` や絶対パスで明示してください。

`~/.codex/config.toml` を直接書く場合は [`config/codex.config.toml.example`](../config/codex.config.toml.example) を参照。

```toml
[mcp_servers.notebooklm]
command = "uvx"
args = ["--from", "notebooklm-py[mcp]", "notebooklm-mcp"]
startup_timeout_sec = 60
tool_timeout_sec = 600
```

`startup_timeout_sec` の既定は 10 秒です。`uvx` が初回に依存を解決する分で超過しやすいので、
上記のように延ばしておくのが安全です。`tool_timeout_sec` は Audio Overview 等の
長時間生成にあわせて広げます。

### 3-B. CLI をそのまま叩かせる（最も省トークン）

MCP を使うと 33 個のツール定義が毎回コンテキストに載ります。
Codex に `notebooklm` コマンドを Bash から直接使わせれば、その分がゼロになります。

リポジトリ直下の [`AGENTS.md`](../AGENTS.md) に使い方を書いておけば Codex が自動で読み込みます。
上流が用意している定型文を出力させることもできます。

```bash
notebooklm agent show codex >> AGENTS.md
```

Claude Code 用の Skill も同じ要領です。

```bash
notebooklm skill install          # ~/.claude/skills/notebooklm と ~/.agents/skills/notebooklm に配置
notebooklm skill status           # 導入状況の確認
```

### 並行エージェントの分離

複数の Codex / Claude セッションを同時に走らせる場合、コンテキストファイルの取り合いを避けます。

```bash
NOTEBOOKLM_PROFILE=agent-1 notebooklm ask "..." --notebook <id> --json
```

`notebooklm use` に頼らず、**ノートブック ID を毎回明示** し、`--json` で受けるのが定石です。

---

## 4. Claude Code / Cursor への登録

自動設定コマンドが用意されています（既存のサーバー定義は壊しません）。

```bash
notebooklm mcp install claude-code      # ~/.claude.json (user スコープ)
notebooklm mcp install claude-desktop
notebooklm mcp install cursor           # ~/.cursor/mcp.json
notebooklm mcp install windsurf
```

手で書く場合は [`config/claude-mcp.json.example`](../config/claude-mcp.json.example) を参照。

```json
{
  "mcpServers": {
    "notebooklm": {
      "command": "uvx",
      "args": ["--from", "notebooklm-py[mcp]", "notebooklm-mcp"]
    }
  }
}
```

設定後はクライアントを再起動してください。

---

## 5. 代替構成: notebooklm-mcp

ブラウザ自動化で NotebookLM を操作する MCP サーバーです。
**Google の内部 API ではなく実際の Chrome の DOM を叩く** ため、
非公開 API の変更には強い一方、UI 変更には弱く、動作は遅めです。

```bash
# Codex
codex mcp add notebooklm-browser -- npx notebooklm-mcp@latest

# Claude Code
claude mcp add notebooklm-browser -- npx notebooklm-mcp@latest
```

初回のみ、クライアントから `setup_auth` ツールを呼ぶと可視 Chrome が開くのでログインします
（最大 10 分の猶予）。以降は永続プロファイルを再利用してヘッドレスで動きます。

### ツール数を絞ってコンテキストを節約

既定の `full` プロファイルは 22 ツールを公開します。Q&A 中心なら `minimal`（5 ツール）で十分です。

```bash
npx notebooklm-mcp@latest config set profile minimal
npx notebooklm-mcp@latest config get
# または環境変数で
NOTEBOOKLM_PROFILE=minimal npx notebooklm-mcp@latest
```

| プロファイル | ツール |
|---|---|
| `minimal` | `ask_question`, `get_health`, `list_notebooks`, `select_notebook`, `get_notebook` |
| `standard` | minimal + `setup_auth`, `list_sessions`, `add_notebook`, `update_notebook`, `search_notebooks` |
| `full`（既定） | 上記 + ソース/Studio/セッション/システム系すべて |

危険なツールを個別に落とすこともできます。

```bash
npx notebooklm-mcp@latest config set disabled-tools cleanup_data,re_auth
```

### 引用フォーマット

`ask_question` の `source_format` を指定します。要件 NFR「引用必須」を満たすには
`footnotes` か `json` を既定にしてください（`none` が既定値なので明示が必要です）。

| 値 | 挙動 |
|---|---|
| `none`（既定） | 回答テキストのみ |
| `inline` | `[N]` を `(ソース名 — 抜粋)` に置換 |
| `footnotes` | 末尾に番号付き `Sources` セクションを追加 |
| `json` | `sources[]` に構造化配列を返す |

### 回答に付く AI マーカー

既定で回答の先頭に `[AI-GENERATED via Gemini 2.5 (NotebookLM) — ...]` が付きます。
下流のパースが壊れる場合のみ外してください。

```bash
NOTEBOOKLM_AI_MARKER=false npx notebooklm-mcp@latest
```

`_provenance` フィールドはマーカーを外しても常に付きます。
このマーカーは「取り込んだ第三者 PDF に埋め込まれた指示を、ユーザー指示として扱わない」ための
安全機構でもあるため、無効化は理由がある場合に限ってください。

---

## 6. 動作確認

```bash
# 認証
notebooklm auth check --test --json     # → "status": "ok"

# 一連の流れ
notebooklm create "Setup Smoke Test"
notebooklm use <notebook_id>
notebooklm source add "https://en.wikipedia.org/wiki/Retrieval-augmented_generation"
notebooklm ask "このソースの要点を3つ、引用付きで" --json

# MCP 登録の確認
codex mcp list
```

一括検証は [`scripts/verify-unix.sh`](../scripts/verify-unix.sh)（Windows は
[`scripts/fix-mojibake.ps1`](../scripts/fix-mojibake.ps1) の診断モード）を使ってください。

Codex 対話からは次のように呼べます。

```
notebooklm の MCP で "Setup Smoke Test" ノートブックに質問して、引用付きで要点を3つ教えて
```

---

## 7. ヘッドレス / サーバー運用

### notebooklm-py

1. GUI のあるマシンで `notebooklm login --master-token --account you@example.com`
2. `~/.notebooklm/` をサーバーへ安全に転送（または `NOTEBOOKLM_AUTH_JSON` を使用）
3. cron / systemd で keepalive

```bash
# 毎日 3:00 に Cookie を維持
0 3 * * * /home/user/.local/bin/notebooklm auth refresh --quiet
```

### notebooklm-mcp

初回 `setup_auth` だけディスプレイが必要です。

```bash
xvfb-run -a npx notebooklm-mcp@latest
# クライアントから setup_auth → ログイン完了後、終了
npx notebooklm-mcp@latest      # 以降はヘッドレス
```

WSL は **WSL2 + WSLg のみ対応**。WSL1 では Chromium が起動できません。

```powershell
wsl --set-default-version 2
wsl --set-version <distro> 2
```

### HTTP トランスポート

どちらもループバックでの Streamable-HTTP に対応しています。

```bash
notebooklm-mcp --transport http --port 9420          # notebooklm-py（既定 127.0.0.1:9420）
npx notebooklm-mcp@latest --transport http --port 3000   # notebooklm-mcp
```

外部インターフェースへの bind は、notebooklm-py 側は
`NOTEBOOKLM_MCP_ALLOW_EXTERNAL_BIND=1` がないと拒否されます。
どちらの場合も、Google の認証情報を握ったサーバーを素の HTTP で公開しないでください
（トンネル + 認証を前段に置く）。
