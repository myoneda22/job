# Windows 文字化け完全対策

要件定義書 §8.2 / FR-008 / §10-3 に対応。

Windows で「文字化け」と呼ばれる症状は **原因が 4 つあり、対策も別々** です。
まず切り分けてから、該当する層だけ直してください。
一括適用は [`scripts/fix-mojibake.ps1`](../scripts/fix-mojibake.ps1)（診断 + 修復）で行えます。

---

## 0. まず切り分ける

```powershell
pwsh -NoProfile -File .\scripts\fix-mojibake.ps1          # 診断のみ
pwsh -NoProfile -File .\scripts\fix-mojibake.ps1 -Apply   # 恒久対策を適用
```

手で見る場合:

```powershell
chcp                                    # 932 なら日本語コードページ
$PSVersionTable.PSVersion               # 5.1 か 7.x か
[Console]::OutputEncoding.WebName       # utf-8 が理想
$env:PYTHONUTF8                         # 1 が理想
python -c "import sys,locale; print(sys.stdout.encoding, locale.getpreferredencoding())"
```

| 症状 | 原因層 | 対策 |
|---|---|---|
| `UnicodeEncodeError: 'cp932' codec can't encode character` で**落ちる** | ① Python の出力エンコーディング | [§1](#1-python-側最重要) |
| 画面に `譁�蟄怜喧縺�` のような日本語崩れ / `?` が出る（落ちはしない） | ② コンソールのコードページ | [§2](#2-コンソール側) |
| `notebooklm ask ... > out.md` したファイルが他ツールで文字化け | ③ リダイレクト時のファイルエンコーディング | [§3](#3-ファイル出力側見落としやすい) |
| 日本語が全部 `□`（豆腐）になる | ④ コンソールフォント | [§4](#4-フォント) |

---

## 1. Python 側（最重要）

### 原因

Windows の Python は、非英語ロケールでは標準出力に **cp932（日本語）/ cp950（繁体字）** を使います。
`✓` や絵文字、一部の記号は cp932 に存在しないため、Rich のテーブルやステータス表示が
`UnicodeEncodeError` で例外になります（notebooklm-py の既知 issue #75 / #80）。

### 対策

notebooklm-py は **CLI 起動時に `PYTHONUTF8=1` を自動設定** するため、`notebooklm` コマンドを
使っている限りこの問題は原則発生しません。問題が起きるのは以下のケースです。

- notebooklm-py を **Python API として** 自作スクリプトから使っている
- 他の Python ツール（自作の後処理スクリプト等）をパイプで繋いでいる
- 古いバージョンを使っている

恒久対策としてユーザー環境変数に入れておくのが確実です。

```powershell
# 恒久（ユーザー環境変数。新しいシェルから有効）
[Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'User')
[Environment]::SetEnvironmentVariable('PYTHONIOENCODING', 'utf-8', 'User')

# 現在のセッションにも即反映
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
```

単発なら実行時フラグでも同じです。

```powershell
python -X utf8 your_script.py
```

Python API を直接使う場合は、コード側でも保険をかけられます。

```python
import sys

if sys.platform == "win32":
    # Python 3.7+：標準出入力を UTF-8 に張り替える
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
```

> **関連**: Sandboxie 等のサンドボックス環境で CLI が無応答になる既知問題があります。
> notebooklm-py は CLI 起動時に `WindowsSelectorEventLoopPolicy` を自動設定して回避しますが、
> Python API を直接使う場合は自分で設定してください。
>
> ```python
> import asyncio, sys
> if sys.platform == "win32":
>     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
> ```

---

## 2. コンソール側

### 一時的（現在のセッションのみ）

```powershell
chcp 65001
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
```

### 恒久（PowerShell プロファイル）

```powershell
# プロファイルが無ければ作る
if (-not (Test-Path $PROFILE)) { New-Item -ItemType File -Path $PROFILE -Force | Out-Null }

@'
# --- NotebookLM / UTF-8 settings ---
$OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new()
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
$PSDefaultParameterValues['Set-Content:Encoding'] = 'utf8'
$PSDefaultParameterValues['Add-Content:Encoding'] = 'utf8'
'@ | Add-Content -Path $PROFILE -Encoding utf8
```

### システム全体（最終手段）

Windows 10 1903+ の「ワールドワイド言語サポートで Unicode UTF-8 を使用」を有効にすると、
システムの ANSI コードページが UTF-8 になります。

`設定 → 時刻と言語 → 言語と地域 → 管理用言語の設定 → システム ロケールの変更 →
「ベータ: ワールドワイド言語サポートで Unicode UTF-8 を使用」にチェック → 再起動`

> ⚠️ この設定は **システム全体に影響** します。cp932 前提の古い業務アプリが文字化けする
> 副作用が知られているため、他の対策で解決しない場合の最終手段としてください。

---

## 3. ファイル出力側（見落としやすい）

**Windows PowerShell 5.1 の `>` リダイレクトは UTF-16LE で書き込みます。**
画面表示は正常なのにファイルだけ化ける、という現象の典型的な原因です。

```powershell
# ❌ PowerShell 5.1 では UTF-16LE になる
notebooklm ask "要約して" > summary.md

# ✅ 明示的に UTF-8
notebooklm ask "要約して" | Out-File -FilePath summary.md -Encoding utf8

# ✅ BOM なし UTF-8 が必要なとき（PowerShell 7+）
notebooklm ask "要約して" | Out-File -FilePath summary.md -Encoding utf8NoBOM
```

PowerShell 7 以降は既定が BOM なし UTF-8 なので、この問題は起きません。
**可能なら PowerShell 7 を使ってください。**

```powershell
winget install Microsoft.PowerShell
```

5.1 を使い続ける場合は、プロファイルに既定値を入れておきます（[§2](#恒久powershell-プロファイル) のスニペットに含まれています）。

```powershell
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
```

### 長いプロンプトはファイルから渡す

コマンドラインに長い日本語を直接書くとクォート地獄とエンコーディング事故の元です。
notebooklm-py は `--prompt-file` に対応しています。

```powershell
# UTF-8 でプロンプトを保存して渡す
Set-Content -Path .\prompts\q.md -Value $question -Encoding utf8
notebooklm ask --prompt-file .\prompts\q.md --json
```

本キットの [`prompts/`](../prompts/) 以下のファイルはそのまま `--prompt-file` に渡せます。

---

## 4. フォント

レガシーな `コマンド プロンプト` / `Windows PowerShell` ウィンドウのラスターフォントは
日本語や記号を描画できず、`□`（豆腐）になります。

- **推奨: Windows Terminal を使う**（`winget install Microsoft.WindowsTerminal`）
- レガシーコンソールを使う場合: タイトルバー右クリック → プロパティ → フォント →
  `MS ゴシック` / `Cascadia Mono` / `Consolas` などの TrueType フォントを選択

---

## 5. Git / エディタ側

コミットしたファイル名や差分が化ける場合:

```bash
git config --global core.quotepath false
git config --global i18n.commitEncoding utf-8
git config --global i18n.logOutputEncoding utf-8
```

VS Code は `files.encoding` を `utf8`、`files.autoGuessEncoding` を `true` にしておくと
既存の cp932 ファイルも読めます。

---

## 6. 検証

```powershell
# 1. 環境
chcp                                  # 65001
$env:PYTHONUTF8                       # 1
python -c "import sys; print(sys.stdout.encoding)"   # utf-8

# 2. 記号と日本語が壊れないか
python -c "print('✓ 日本語テスト ★ 絵文字 🎧')"

# 3. 実際の CLI 出力
notebooklm auth check --test --json

# 4. ファイル出力のエンコーディング確認（先頭バイトを見る）
notebooklm list | Out-File -FilePath .\enc-test.txt -Encoding utf8
Format-Hex .\enc-test.txt -Count 8
#   EF BB BF で始まる → UTF-8 (BOM 付き)
#   FF FE       で始まる → UTF-16LE（対策が効いていない）
Remove-Item .\enc-test.txt
```

`scripts/fix-mojibake.ps1` はこの検証を自動で行い、各層の合否を表で出します。

---

## 7. Codex に自動修復させる場合

要件定義書 §8.2 の「Codex に指示して自動修正」を行う場合のプロンプト雛形:

```
このリポジトリの docs/04-windows-encoding.md を読んで、現在の Windows 環境の
文字化け対策状況を diagnose し、不足している層だけを修正してください。

手順:
1. scripts/fix-mojibake.ps1 を診断モードで実行し、結果を報告
2. 失敗している層を特定（Python / コンソール / ファイル出力 / フォント）
3. システムロケールの UTF-8 化（副作用が大きい）は提案のみで、実行はしない
4. それ以外の層を修正し、docs/04 §6 の検証コマンドで確認
```

---

## 補足: Windows で「文字化け」ではないのに文字化けに見える問題

| 症状 | 実際の原因 | 対処 |
|---|---|---|
| `Missing required cookies: __Secure-1PSIDTS` | Chrome 127+ の App-Bound Encryption で Cookie を復号できない | Firefox を Cookie ソースにする / master-token を使う（[07](07-troubleshooting.md#windows-認証が通らない)） |
| `BrowserType.launch_persistent_context: spawn UNKNOWN` | AppLocker / WDAC / ウイルス対策が Playwright の Chromium 実行をブロック | `--browser chrome` / `--browser msedge` を使う、または IT に `%LOCALAPPDATA%\ms-playwright` の許可を依頼 |
| CLI が無応答のまま固まる | サンドボックス環境での `ProactorEventLoop` ブロック | [§1 の補足](#1-python-側最重要) 参照 |
