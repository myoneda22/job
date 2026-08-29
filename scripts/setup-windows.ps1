#Requires -Version 5.1
<#
.SYNOPSIS
    Codex × NotebookLM 連携キット — Windows セットアップ。

.DESCRIPTION
    文字化け対策 → uv / notebooklm-py の導入 → Google 認証 → MCP 登録 までを一括で行います。
    既に済んでいる手順はスキップするので、何度実行しても安全です。

.PARAMETER WithBrowser
    フォールバック構成の notebooklm-mcp（Node / Chrome 自動化）も準備します。

.PARAMETER NoLogin
    Google 認証をスキップします（あとで notebooklm login）。

.PARAMETER DryRun
    実行せず、行う操作を表示するだけにします。

.EXAMPLE
    pwsh -File .\scripts\setup-windows.ps1

.EXAMPLE
    pwsh -File .\scripts\setup-windows.ps1 -WithBrowser

.LINK
    docs/02-setup-codex.md
#>
[CmdletBinding()]
param(
    [switch] $WithBrowser,
    [switch] $NoLogin,
    [switch] $DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# PowerShell 5.1 には $IsWindows が無い（短絡評価で参照を避ける）
$isWin = ($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows

function Write-Step { param([string] $Text) Write-Host ''; Write-Host "==> $Text" -ForegroundColor Cyan }
function Write-Ok   { param([string] $Text) Write-Host "  OK   $Text" -ForegroundColor Green }
function Write-Warn { param([string] $Text) Write-Host "  WARN $Text" -ForegroundColor Yellow }
function Write-Info { param([string] $Text) Write-Host "       $Text" -ForegroundColor DarkGray }
function Write-Fail { param([string] $Text) Write-Host "  FAIL $Text" -ForegroundColor Red }

function Test-Cmd { param([string] $Name) return [bool] (Get-Command $Name -ErrorAction SilentlyContinue) }

function Invoke-Step {
    param(
        [Parameter(Mandatory)][string] $Exe,
        [Parameter(Mandatory)][string[]] $Args
    )
    $display = "$Exe $($Args -join ' ')"
    if ($DryRun) {
        Write-Host "  [dry-run] $display" -ForegroundColor DarkGray
        return $true
    }
    Write-Host "  `$ $display" -ForegroundColor DarkGray
    & $Exe @Args
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "コマンドが失敗しました (exit $LASTEXITCODE): $display"
        return $false
    }
    return $true
}

Write-Host 'Codex × NotebookLM 連携キット — Windows セットアップ' -ForegroundColor Cyan
Write-Host "PowerShell $($PSVersionTable.PSVersion)"

if (-not $isWin) {
    Write-Warn 'Windows 以外で実行されています。macOS / Linux では scripts/setup-unix.sh を使ってください。'
}

# ---------------------------------------------------------------------------
# 1. 文字化け対策（他の手順より先に。導入時のログが読めなくなるため）
# ---------------------------------------------------------------------------
Write-Step '文字化け対策を適用します (docs/04)'

if ($DryRun) {
    Write-Host '  [dry-run] fix-mojibake.ps1 -Apply' -ForegroundColor DarkGray
} else {
    $fixScript = Join-Path $PSScriptRoot 'fix-mojibake.ps1'
    if (Test-Path $fixScript) {
        & $fixScript -Apply
    } else {
        Write-Warn "fix-mojibake.ps1 が見つかりません。最低限の設定のみ適用します。"
        if ($isWin) {
            [Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'User')
            [Environment]::SetEnvironmentVariable('PYTHONIOENCODING', 'utf-8', 'User')
        }
        $env:PYTHONUTF8 = '1'
        $env:PYTHONIOENCODING = 'utf-8'
    }
}

if ($PSVersionTable.PSVersion.Major -lt 6) {
    Write-Warn "Windows PowerShell $($PSVersionTable.PSVersion) を使っています。"
    Write-Info "'>' リダイレクトが UTF-16LE になるため、PowerShell 7 を推奨します:"
    Write-Info '  winget install Microsoft.PowerShell'
}

# ---------------------------------------------------------------------------
# 2. 前提条件
# ---------------------------------------------------------------------------
Write-Step '前提条件を確認します'

$pythonCmd = $null
foreach ($candidate in @('python', 'python3', 'py')) {
    if (Test-Cmd $candidate) { $pythonCmd = $candidate; break }
}
if ($pythonCmd) {
    $pv = (& $pythonCmd -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>&1 | Out-String).Trim()
    Write-Ok "Python $pv ($pythonCmd)"
} else {
    Write-Warn 'Python が見つかりません。uv が管理する Python でも動作します。'
    Write-Info '手動で入れる場合: winget install Python.Python.3.12'
}

if (Test-Cmd 'uv') {
    Write-Ok "uv ($((Get-Command uv).Source))"
} else {
    Write-Warn 'uv が見つかりません。導入します。'
    if (Test-Cmd 'winget') {
        if (-not (Invoke-Step 'winget' @('install', '--id', 'astral-sh.uv', '-e', '--source', 'winget'))) {
            Write-Fail 'uv の導入に失敗しました。手動で導入してから再実行してください。'
            Write-Info '  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"'
            exit 1
        }
        Write-Info 'PATH を反映するため、新しいシェルで本スクリプトを再実行してください。'
        exit 0
    } else {
        Write-Fail 'winget が使えません。次のコマンドで uv を導入してから再実行してください。'
        Write-Info '  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"'
        exit 1
    }
}

if ($WithBrowser) {
    if (Test-Cmd 'node') {
        $nodeMajor = [int]((& node -p 'process.versions.node.split(".")[0]' 2>&1 | Out-String).Trim())
        if ($nodeMajor -ge 18) {
            Write-Ok "Node.js $((& node -v 2>&1 | Out-String).Trim())"
        } else {
            Write-Fail "Node.js 18 以上が必要です（現在 $nodeMajor）。"
            exit 1
        }
    } else {
        Write-Fail '-WithBrowser には Node.js 18+ が必要です（winget install OpenJS.NodeJS.LTS）。'
        exit 1
    }
}

$hasCodex  = Test-Cmd 'codex'
$hasClaude = Test-Cmd 'claude'
if ($hasCodex)  { Write-Ok 'Codex CLI を検出' }
if ($hasClaude) { Write-Ok 'Claude Code を検出' }
if (-not $hasCodex -and -not $hasClaude) {
    Write-Warn 'codex / claude が見つかりません。MCP 登録は手動で行ってください（config/ に雛形あり）。'
}

# ---------------------------------------------------------------------------
# 3. notebooklm-py
# ---------------------------------------------------------------------------
Write-Step 'notebooklm-py を導入します'

if ((Test-Cmd 'notebooklm') -and -not $DryRun) {
    Write-Ok "既に導入済み: $((Get-Command notebooklm).Source)"
    Write-Info '更新する場合: uv tool upgrade notebooklm-py'
} else {
    if (-not (Invoke-Step 'uv' @('tool', 'install', 'notebooklm-py[browser,mcp]'))) {
        Write-Fail 'notebooklm-py の導入に失敗しました。'
        exit 1
    }
}

# ---------------------------------------------------------------------------
# 4. 認証
# ---------------------------------------------------------------------------
Write-Step 'Google 認証'

if ($NoLogin) {
    Write-Info '認証をスキップしました。あとで実行してください: notebooklm login'
} elseif ($DryRun) {
    Write-Host '  [dry-run] notebooklm auth check --test --json' -ForegroundColor DarkGray
} elseif (-not (Test-Cmd 'notebooklm')) {
    Write-Warn 'notebooklm コマンドが PATH にありません。新しいシェルを開いて再実行してください。'
} else {
    $null = & notebooklm auth check --test --json 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Ok '認証済みです'
    } else {
        Write-Warn '未認証です。ブラウザが開くので Google にサインインしてください。'
        & notebooklm login
        if ($LASTEXITCODE -ne 0) {
            Write-Fail 'ログインに失敗しました。Windows でよくある原因と対処:'
            Write-Info '  Cookie を復号できない (App-Bound Encryption):'
            Write-Info '    notebooklm login --browser-cookies firefox'
            Write-Info '  ブラウザが起動しない (spawn UNKNOWN):'
            Write-Info '    notebooklm login --browser chrome    /    --browser msedge'
            Write-Info '  無人運用にしたい:'
            Write-Info '    notebooklm login --master-token --account you@example.com'
            Write-Info '  詳細: docs/07-troubleshooting.md'
        }
    }
}

# ---------------------------------------------------------------------------
# 5. notebooklm-mcp（任意）
# ---------------------------------------------------------------------------
if ($WithBrowser) {
    Write-Step 'notebooklm-mcp（フォールバック構成）を準備します'
    $null = Invoke-Step 'npx' @('--yes', 'notebooklm-mcp@latest', '--version')
    Write-Info '初回ログインは、クライアントから setup_auth ツールを呼んで行います。'
    Write-Info 'Chrome が起動しない場合は環境変数 BROWSER_CHANNEL=chromium を設定してください。'
}

# ---------------------------------------------------------------------------
# 6. MCP 登録
# ---------------------------------------------------------------------------
Write-Step 'エージェントに MCP サーバーを登録します'

if ($hasCodex) {
    $already = $false
    if (-not $DryRun) {
        $listOut = (& codex mcp list 2>&1 | Out-String)
        if ($listOut -match '(?m)^\s*notebooklm\b') { $already = $true }
    }
    if ($already) {
        Write-Ok 'codex: notebooklm は登録済み'
    } else {
        $null = Invoke-Step 'codex' @('mcp', 'add', 'notebooklm', '--', 'uvx', '--from', 'notebooklm-py[mcp]', 'notebooklm-mcp')
    }
    if ($WithBrowser) {
        $null = Invoke-Step 'codex' @('mcp', 'add', 'notebooklm-browser', '--', 'npx', 'notebooklm-mcp@latest')
    }
    Write-Warn '~/.codex/config.toml に startup_timeout_sec / tool_timeout_sec の追記を推奨します。'
    Write-Info '雛形: config/codex.config.toml.example'
}

if ($hasClaude) {
    if ($DryRun) {
        Write-Host '  [dry-run] notebooklm mcp install claude-code' -ForegroundColor DarkGray
    } elseif (Test-Cmd 'notebooklm') {
        & notebooklm mcp install claude-code
        if ($LASTEXITCODE -ne 0) { Write-Warn 'claude-code への自動設定に失敗しました。config/claude-mcp.json.example を参照してください。' }
    }
    if ($WithBrowser) {
        $null = Invoke-Step 'claude' @('mcp', 'add', 'notebooklm-browser', '--', 'npx', 'notebooklm-mcp@latest')
    }
}

# ---------------------------------------------------------------------------
# 7. 完了
# ---------------------------------------------------------------------------
Write-Host ''
Write-Host '────────────────────────────────────────────────'
Write-Host 'セットアップが完了しました。' -ForegroundColor Green
Write-Host ''
Write-Host '  1. 新しいシェルを開く（環境変数と PATH の反映のため）'
Write-Host '  2. 診断:     pwsh -NoProfile -File .\scripts\fix-mojibake.ps1'
Write-Host '  3. 動作確認: notebooklm create "Setup Smoke Test"'
Write-Host '               notebooklm ask "テストです" --notebook <id> --json'
Write-Host '  4. MCP を使うにはクライアントを再起動してください。'
Write-Host ''
Write-Host '  ドキュメント:'
Write-Host '    セットアップ詳細    docs/02-setup-codex.md'
Write-Host '    ツール選定の根拠    docs/03-comparison.md'
Write-Host '    文字化け対策        docs/04-windows-encoding.md'
Write-Host '    プロンプト集        docs/05-prompt-templates.md'
Write-Host '    困ったとき          docs/07-troubleshooting.md'
Write-Host '────────────────────────────────────────────────'
