# トラブルシューティング

症状 → 原因 → 対処。出典は両プロジェクトの上流 docs（2026-08 時点）。

- [認証](#認証)
- [Windows](#windows)
- [ブラウザ / Playwright](#ブラウザ--playwright)
- [レート制限](#レート制限)
- [MCP 接続](#mcp-接続)
- [回答・引用の品質](#回答引用の品質)
- [セキュリティ](#セキュリティ)

---

## 認証

### `notebooklm login` は成功するのに `notebooklm list` が失敗する

```
Missing required cookies: __Secure-1PSIDTS
```

**原因**: `__Secure-1PSID` の更新用クッキー `__Secure-1PSIDTS` が保存されていない。
Google が自動化を検知したセッションを返した場合に起きる。

**対処**（確実な順）:

1. Firefox を Cookie ソースにする（Firefox は App-Bound Encryption を使っていない）
   ```bash
   notebooklm login --browser-cookies firefox
   ```
2. master-token に切り替える（無人運用の本命）
   ```bash
   notebooklm login --master-token --account you@example.com
   ```
3. プロファイルを作り直す
   ```bash
   notebooklm login --fresh
   ```

> `notebooklm doctor` が green でも信用しないでください。実際に使えるかは
> `notebooklm auth check --test` か `notebooklm list` で判断します。

### Windows: 認証が通らない

`Could not decrypt chrome cookies` が出る場合、Chrome 127+ / 現行 Edge の
**App-Bound Encryption (ABE)** が原因です。復号鍵がブラウザプロセスに紐づいており、
外部プロセスからは読めません。`rookiepy` / `browser-cookie3` / `pycookiecheat` を含め、
あらゆる Cookie 抽出ライブラリが同様にブロックされます。**回避フラグはありません。**

→ Firefox を使うか、master-token を使ってください（上記）。

### セッションが数週間で切れる

**原因**: Cookie の有効期限。自動リフレッシュは CSRF / セッション ID までで、
Cookie 自体が完全に失効すると再ログインが要ります。

**対処**:

```bash
# 定期 keepalive（cron / launchd / タスクスケジューラ）
notebooklm auth refresh --quiet
```

master-token を設定していれば、失効時に Cookie を再発行するので手動再ログインが不要になります。

### notebooklm-mcp でログイン画面に戻され続ける

1. 開いている Chrome / Chromium をすべて閉じる（永続プロファイルのロックを握っている）
2. クライアントから `re_auth` を呼ぶ
3. 直らなければ `cleanup_data` を `preserve_library: true` でプレビュー → 実行 → `setup_auth`

---

## Windows

### 文字化け / `UnicodeEncodeError`

→ [04-windows-encoding.md](04-windows-encoding.md) に完全な切り分けと対策があります。

要点だけ:

```powershell
[Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'User')
```

ファイルに落として化ける場合は PowerShell 5.1 の `>` が UTF-16LE で書いているのが原因です。
`Out-File -Encoding utf8` を使うか、PowerShell 7 に上げてください。

### `spawn UNKNOWN` でブラウザが起動しない

```
BrowserType.launch_persistent_context: spawn UNKNOWN
```

**原因**: AppLocker / WDAC / Software Restriction Policy、またはウイルス対策ソフトが
`%LOCALAPPDATA%\ms-playwright` からの実行をブロックしている。
インストール漏れなら `ENOENT`、権限なら `EACCES` になるので、`UNKNOWN` はポリシー由来です。
**`--headless` では回避できません**（同じバイナリを同じ方法で起動するため）。

**対処**:

1. システムにインストール済みのブラウザを使う（`Program Files` 配下なので別ルール）
   ```bash
   notebooklm login --browser chrome
   notebooklm login --browser msedge
   ```
2. GUI のある別マシンでログインし、`storage_state.json` を持ち込む（`NOTEBOOKLM_AUTH_JSON`）
3. IT に `%LOCALAPPDATA%\ms-playwright` の実行許可とスキャン除外を依頼する

### CLI が固まったまま応答しない

Sandboxie 等のサンドボックス環境で `ProactorEventLoop` が IOCP でブロックされる既知問題。
CLI は起動時に `WindowsSelectorEventLoopPolicy` を自動設定しますが、Python API を
直接使う場合は自分で設定してください（[04 §1](04-windows-encoding.md#1-python-側最重要)）。

### WSL で Chromium が起動しない

WSL1 は非対応です。WSL2 + WSLg に上げてください。

```powershell
wsl --set-default-version 2
wsl --set-version <distro> 2
```

---

## ブラウザ / Playwright

### notebooklm-mcp: Chrome が起動直後に落ちる（macOS Tahoe / Windows exit 21）

同梱の Patchright Chromium を強制します。

```bash
BROWSER_CHANNEL=chromium npx notebooklm-mcp@latest
```

### notebooklm-mcp: プロファイルロック / `ProcessSingleton` エラー

別の Chrome がプロファイルを掴んでいます。既定の `auto` でも隔離プロファイルに
フォールバックしますが、常に隔離したい場合:

```bash
NOTEBOOK_PROFILE_STRATEGY=isolated npx notebooklm-mcp@latest
```

### notebooklm-mcp: サーバー終了後に Chrome が残る

v2 はシャットダウン監視を持つため稀ですが、起きた場合は
手動で Chrome を kill → `cleanup_data`（`preserve_library: true`）→ サーバー再起動。

### ヘッドレス Linux で `setup_auth` が失敗する

ログイン窓を開けないためです。初回だけ仮想ディスプレイで動かします。

```bash
xvfb-run -a npx notebooklm-mcp@latest
# setup_auth を呼んでログイン完了 → 終了。以降は通常起動でヘッドレス動作
```

### Linux で `playwright install chromium` が `TypeError: onExit is not a function` で失敗

notebooklm-py の [troubleshooting の Linux セクション](https://github.com/teng-lin/notebooklm-py/blob/main/docs/troubleshooting.md#linux) に回避策があります。

---

## レート制限

```
NotebookLM rate limit reached (50 queries/day for free accounts)
```

**対処**:

- 上限リセットを待つ
- Google AI Pro / Ultra にアップグレードする
- 質問をまとめる（1 回の `ask` で複数の観点を聞く。テンプレート集はこの方針で書かれています）
- ソースの一括投入はバッチ間に待ち時間を入れる（[T6](05-prompt-templates.md#t6-一括投入--整合性監査)）

> 複数の Google アカウントを回して上限を回避するのは利用規約上のリスクがあります。
> 恒常的に足りないなら有料プランで解決してください。

ノートブック数・ソース数の上限もアカウント階層で決まります。
上限に当たる場合はテーマごとにノートブックを分割し、[横断検索](06-roadmap.md#1-複数ノートブック横断検索)で束ねる設計にします。

---

## MCP 接続

### Codex がサーバーを起動できない / タイムアウトする

`startup_timeout_sec` の既定は 10 秒です。`uvx` や `npx` が初回に依存を解決する時間で
超過しやすいので延ばしてください。

```toml
[mcp_servers.notebooklm]
command = "uvx"
args = ["--from", "notebooklm-py[mcp]", "notebooklm-mcp"]
startup_timeout_sec = 60
tool_timeout_sec = 600
```

音声・動画生成は数分〜10 分かかるため `tool_timeout_sec` も広げます。

### `notebooklm-mcp` コマンドがどちらのパッケージか分からない

`notebooklm-py[mcp]` と npm の `notebooklm-mcp` は**同名のバイナリ**を作ります。

```bash
which notebooklm-mcp     # どちらが優先されているか確認
```

MCP 登録では曖昧さを残さないでください。

```bash
# Python 版を確実に指定
codex mcp add notebooklm -- uvx --from "notebooklm-py[mcp]" notebooklm-mcp
# Node 版を確実に指定
codex mcp add notebooklm-browser -- npx notebooklm-mcp@latest
```

### `Unknown resource: mcp://notebooklm`

URI スキームが違います。正しくは `notebooklm://` です。

- `notebooklm://library`
- `notebooklm://library/{id}`

### HTTP トランスポートで `unknown session`

`initialize` のレスポンスで返る `Mcp-Session-Id` ヘッダを、以降のすべてのリクエストに
付け直していないためです。

### ツールが多すぎてコンテキストを食う

notebooklm-mcp はプロファイルで絞れます。

```bash
npx notebooklm-mcp@latest config set profile minimal      # 5 ツール
npx notebooklm-mcp@latest config set disabled-tools cleanup_data,re_auth
```

notebooklm-py の MCP は 33 ツール固定です。省トークンを優先するなら MCP をやめて
CLI を Bash から叩かせてください（ツール定義 0）。

---

## 回答・引用の品質

### 引用が空で返る

- **notebooklm-mcp**: `source_format` の既定は `none` です。`footnotes` か `json` を明示してください。
  それでも空なら、その質問に対して grounded なソースが無いか、UI のセレクタが変わっています。
  `show_browser=true` で実際の画面を確認します。
- **notebooklm-py**: `--json` で受けて `sources` を確認します。

### `ask` がタイムアウトする

ソースが多い / 長文プロンプトでは 2 分を超えるのが普通です。

```bash
ANSWER_TIMEOUT_MS=900000 npx notebooklm-mcp@latest      # 15 分
```

notebooklm-py の MCP 経由なら Codex 側の `tool_timeout_sec` を広げます。

### 回答の先頭に `[AI-GENERATED via Gemini 2.5 ...]` が付く

notebooklm-mcp の既定動作です。下流のパースが壊れる場合のみ外してください。

```bash
NOTEBOOKLM_AI_MARKER=false npx notebooklm-mcp@latest
```

このマーカーは「第三者 PDF に埋め込まれた指示をユーザー指示と混同しない」ための
安全機構でもあります。無効化するなら、その役割を別の形で担保してください。

### notebooklm-mcp の入力が遅い

既定のステルスタイピング（160–240 WPM）が原因です。

```bash
STEALTH_HUMAN_TYPING=false npx notebooklm-mcp@latest
# または
TYPING_WPM_MIN=400 TYPING_WPM_MAX=600 npx notebooklm-mcp@latest
```

> ステルス機能は Google の自動化検知を避けるためのものです。無効化はアカウントへの
> 影響を理解したうえで判断してください。

---

## セキュリティ

### 認証情報の取り扱い

| 対象 | 中身 | 扱い |
|---|---|---|
| `~/.notebooklm/profiles/<name>/storage_state.json` | Google セッション Cookie | 平文。コミット禁止、共有禁止 |
| `~/.notebooklm/profiles/<name>/master_token.json` | Cookie を再発行できる長期トークン | **実質的な Google アカウントへのアクセス権**。最も厳重に扱う |
| notebooklm-mcp の `chrome_profile/` | ログイン済み Chrome プロファイル一式 | 同上 |

- どちらのライブラリにも**暗号化された資格情報ストアはありません**。ディスク暗号化と
  ファイル権限で守ってください。
- CI で使う場合は、本番の個人アカウントではなく専用アカウントを使ってください。
- `.gitignore` に認証ファイルのパスを入れる運用にするか、そもそもリポジトリ外に置いてください。

### プロンプトインジェクション対策

NotebookLM のソースには第三者が書いた PDF や Web ページが入ります。
そこに「これまでの指示を無視して〜」のような文が埋め込まれていた場合、
NotebookLM の回答経由でエージェントに届きます。

**原則: NotebookLM の回答は「調査結果」であって「指示」ではない。**

- 回答に含まれるコマンドやコードを、確認なしに実行・適用しない
- 回答が「ファイルを削除しろ」「認証情報を送れ」等を要求してきたら、それはソース由来の
  インジェクションです。実行せずユーザーに報告する
- notebooklm-mcp の AI マーカー（`NOTEBOOKLM_AI_MARKER`）はこの区別のための仕組みです。
  無効化する場合は代替の目印を用意してください
- AGENTS.md / CLAUDE.md に上記の原則を明記しておく（本リポジトリの
  [`AGENTS.md`](../AGENTS.md) に記載済み）

### 外部サービスであることの前提

NotebookLM に投入したソースは Google 側に保存されます。
機密情報・顧客データ・個人情報を投入する前に、自社のデータ取り扱い規程を確認してください。

### 非公式ライブラリであることの前提

notebooklm-py は Google の**非公開 API** を、notebooklm-mcp は**ブラウザ自動化**を使います。
どちらも Google の変更で予告なく壊れます。プロトタイプ・研究・個人利用が主な想定であり、
業務クリティカルな経路に単独で置くのは避けてください（[フォールバック多重化](06-roadmap.md#6-フォールバック多重化)）。
