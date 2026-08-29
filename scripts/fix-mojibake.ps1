#Requires -Version 5.1
<#
.SYNOPSIS
    Windows の文字化けを診断し、恒久対策を適用します。

.DESCRIPTION
    「文字化け」には原因の異なる 4 つの層があります。本スクリプトは各層を個別に
    診断し、-Apply を付けたときだけ修復します。診断は読み取り専用です。

      層 1  Python の出力エンコーディング  … UnicodeEncodeError で落ちる
      層 2  コンソールのコードページ        … 画面表示が崩れる
      層 3  ファイル出力のエンコーディング  … 保存したファイルだけ化ける
      層 4  コンソールフォント              … 日本語が □ になる

    システムロケールの UTF-8 化（副作用が大きい）は診断・案内のみで、
    本スクリプトからは変更しません。

.PARAMETER Apply
    修復を実行します。省略時は診断のみ。

.PARAMETER Scope
    環境変数の適用範囲。User（既定）または Process。

.EXAMPLE
    pwsh -NoProfile -File .\scripts\fix-mojibake.ps1

.EXAMPLE
    pwsh -NoProfile -File .\scripts\fix-mojibake.ps1 -Apply

.LINK
    docs/04-windows-encoding.md
#>
[CmdletBinding()]
param(
    [switch] $Apply,
    [ValidateSet('User', 'Process')]
    [string] $Scope = 'User'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# PowerShell 5.1 は Windows 専用なので $IsWindows が存在しない（短絡評価で参照を避ける）
$script:IsWindowsHost = ($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows

if (-not $script:IsWindowsHost) {
    Write-Warning 'Windows 以外で実行されています。診断は動きますが、結果は Windows の実態を反映しません。'
    if ($Apply -and $Scope -eq 'User') {
        Write-Warning "ユーザー環境変数の永続化は Windows のみ対応です。-Scope Process に切り替えます。"
        $Scope = 'Process'
    }
}

$script:Results = New-Object System.Collections.Generic.List[object]

function Add-Result {
    param(
        [Parameter(Mandatory)][string] $Layer,
        [Parameter(Mandatory)][string] $Check,
        [Parameter(Mandatory)][ValidateSet('PASS', 'FAIL', 'WARN', 'INFO')][string] $Status,
        [string] $Detail = '',
        [string] $Fix = ''
    )
    $script:Results.Add([pscustomobject]@{
        Layer  = $Layer
        Check  = $Check
        Status = $Status
        Detail = $Detail
        Fix    = $Fix
    })
}

function Write-Head {
    param([string] $Text)
    Write-Host ''
    Write-Host "── $Text ──" -ForegroundColor DarkGray
}

function Test-CommandExists {
    param([string] $Name)
    return [bool] (Get-Command $Name -ErrorAction SilentlyContinue)
}

# ============================================================================
# 診断
# ============================================================================

Write-Host 'Windows 文字化け診断' -ForegroundColor Cyan
Write-Host "PowerShell $($PSVersionTable.PSVersion)  /  $([System.Environment]::OSVersion.VersionString)"

# --- 層 1: Python ------------------------------------------------------------
Write-Head '層 1: Python の出力エンコーディング'

$pythonUtf8Proc = $env:PYTHONUTF8
$pythonUtf8User = [Environment]::GetEnvironmentVariable('PYTHONUTF8', 'User')
$pythonIoUser   = [Environment]::GetEnvironmentVariable('PYTHONIOENCODING', 'User')

if ($pythonUtf8Proc -eq '1') {
    Add-Result -Layer 1 -Check 'PYTHONUTF8 (現セッション)' -Status PASS -Detail '1'
} else {
    Add-Result -Layer 1 -Check 'PYTHONUTF8 (現セッション)' -Status FAIL `
        -Detail "未設定または '$pythonUtf8Proc'" -Fix '$env:PYTHONUTF8 = "1"'
}

if ($pythonUtf8User -eq '1') {
    Add-Result -Layer 1 -Check 'PYTHONUTF8 (ユーザー環境変数)' -Status PASS -Detail '1'
} else {
    Add-Result -Layer 1 -Check 'PYTHONUTF8 (ユーザー環境変数)' -Status FAIL `
        -Detail '未設定' -Fix '-Apply で恒久設定します'
}

if ($pythonIoUser -and $pythonIoUser.ToLower() -like 'utf-8*') {
    Add-Result -Layer 1 -Check 'PYTHONIOENCODING (ユーザー環境変数)' -Status PASS -Detail $pythonIoUser
} else {
    Add-Result -Layer 1 -Check 'PYTHONIOENCODING (ユーザー環境変数)' -Status WARN `
        -Detail '未設定' -Fix '-Apply で utf-8 を設定します'
}

$pythonCmd = $null
foreach ($candidate in @('python', 'python3', 'py')) {
    if (Test-CommandExists $candidate) { $pythonCmd = $candidate; break }
}

if ($pythonCmd) {
    try {
        $stdoutEnc = (& $pythonCmd -c "import sys; print(sys.stdout.encoding)" 2>&1 | Out-String).Trim()
        if ($stdoutEnc -match '(?i)utf-?8') {
            Add-Result -Layer 1 -Check 'Python sys.stdout.encoding' -Status PASS -Detail $stdoutEnc
        } else {
            Add-Result -Layer 1 -Check 'Python sys.stdout.encoding' -Status FAIL `
                -Detail $stdoutEnc -Fix 'PYTHONUTF8=1 を設定、または python -X utf8'
        }
    } catch {
        Add-Result -Layer 1 -Check 'Python sys.stdout.encoding' -Status WARN -Detail '取得に失敗しました'
    }

    try {
        $null = & $pythonCmd -c "print('OK-NONASCII')" 2>&1
        $nonAscii = (& $pythonCmd -c "print('✓ 日本語 ★')" 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -eq 0 -and $nonAscii -notmatch 'UnicodeEncodeError') {
            Add-Result -Layer 1 -Check '非 ASCII の出力' -Status PASS -Detail $nonAscii
        } else {
            Add-Result -Layer 1 -Check '非 ASCII の出力' -Status FAIL `
                -Detail 'UnicodeEncodeError' -Fix 'PYTHONUTF8=1'
        }
    } catch {
        Add-Result -Layer 1 -Check '非 ASCII の出力' -Status FAIL -Detail $_.Exception.Message -Fix 'PYTHONUTF8=1'
    }
} else {
    Add-Result -Layer 1 -Check 'Python' -Status WARN -Detail 'python が PATH にありません'
}

# --- 層 2: コンソール --------------------------------------------------------
Write-Head '層 2: コンソールのコードページ'

$outCp = [Console]::OutputEncoding.CodePage
$outNm = [Console]::OutputEncoding.WebName
if ($outCp -eq 65001) {
    Add-Result -Layer 2 -Check 'Console::OutputEncoding' -Status PASS -Detail "$outNm (CP$outCp)"
} else {
    Add-Result -Layer 2 -Check 'Console::OutputEncoding' -Status FAIL `
        -Detail "$outNm (CP$outCp)" -Fix '[Console]::OutputEncoding = [Text.UTF8Encoding]::new()'
}

try {
    $psOutCp = $OutputEncoding.CodePage
    if ($psOutCp -eq 65001) {
        Add-Result -Layer 2 -Check '$OutputEncoding (パイプ)' -Status PASS -Detail "CP$psOutCp"
    } else {
        Add-Result -Layer 2 -Check '$OutputEncoding (パイプ)' -Status WARN `
            -Detail "CP$psOutCp" -Fix '$OutputEncoding = [Text.UTF8Encoding]::new()'
    }
} catch {
    Add-Result -Layer 2 -Check '$OutputEncoding (パイプ)' -Status WARN -Detail '判定できません'
}

$acp = [System.Text.Encoding]::Default.CodePage
if ($acp -eq 65001) {
    Add-Result -Layer 2 -Check 'システム ANSI コードページ' -Status PASS -Detail 'CP65001 (UTF-8)'
} else {
    Add-Result -Layer 2 -Check 'システム ANSI コードページ' -Status INFO `
        -Detail "CP$acp" -Fix 'UTF-8 化は副作用が大きいため本スクリプトでは変更しません（docs/04 §2）'
}

# --- 層 3: ファイル出力 ------------------------------------------------------
Write-Head '層 3: ファイル出力のエンコーディング'

if ($PSVersionTable.PSVersion.Major -ge 6) {
    Add-Result -Layer 3 -Check 'PowerShell のバージョン' -Status PASS `
        -Detail "$($PSVersionTable.PSVersion) — リダイレクトの既定は BOM なし UTF-8"
} else {
    Add-Result -Layer 3 -Check 'PowerShell のバージョン' -Status FAIL `
        -Detail "$($PSVersionTable.PSVersion) — '>' の既定は UTF-16LE" `
        -Fix 'PowerShell 7 を使う（winget install Microsoft.PowerShell）か $PSDefaultParameterValues を設定'
}

$tmpFile = Join-Path ([System.IO.Path]::GetTempPath()) ("nblm-enc-{0}.txt" -f ([guid]::NewGuid().ToString('N')))
try {
    "日本語テスト" | Out-File -FilePath $tmpFile
    $bytes = [System.IO.File]::ReadAllBytes($tmpFile)
    $head  = ($bytes | Select-Object -First 4 | ForEach-Object { '{0:X2}' -f $_ }) -join ' '
    if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
        Add-Result -Layer 3 -Check 'Out-File の既定エンコーディング' -Status FAIL `
            -Detail "UTF-16LE (先頭: $head)" `
            -Fix '$PSDefaultParameterValues["Out-File:Encoding"] = "utf8"'
    } elseif ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        Add-Result -Layer 3 -Check 'Out-File の既定エンコーディング' -Status PASS -Detail "UTF-8 BOM 付き (先頭: $head)"
    } else {
        Add-Result -Layer 3 -Check 'Out-File の既定エンコーディング' -Status PASS -Detail "UTF-8 BOM なし (先頭: $head)"
    }
} catch {
    Add-Result -Layer 3 -Check 'Out-File の既定エンコーディング' -Status WARN -Detail $_.Exception.Message
} finally {
    if (Test-Path $tmpFile) { Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue }
}

$profileHasUtf8 = $false
if ($PROFILE -and (Test-Path $PROFILE)) {
    $profileText = Get-Content -Path $PROFILE -Raw -ErrorAction SilentlyContinue
    if ($profileText -and $profileText -match 'PYTHONUTF8') { $profileHasUtf8 = $true }
}
if ($profileHasUtf8) {
    Add-Result -Layer 3 -Check 'PowerShell プロファイル' -Status PASS -Detail 'UTF-8 設定が入っています'
} else {
    Add-Result -Layer 3 -Check 'PowerShell プロファイル' -Status WARN `
        -Detail '未設定' -Fix '-Apply でプロファイルに追記します'
}

# --- 層 4: フォント / ターミナル ---------------------------------------------
Write-Head '層 4: ターミナル'

if ($env:WT_SESSION) {
    Add-Result -Layer 4 -Check 'ターミナル' -Status PASS -Detail 'Windows Terminal'
} else {
    Add-Result -Layer 4 -Check 'ターミナル' -Status WARN `
        -Detail 'レガシーコンソールの可能性' `
        -Fix 'Windows Terminal を推奨（winget install Microsoft.WindowsTerminal）。レガシーの場合はプロパティで TrueType フォントを選択'
}

Write-Host ''
Write-Host '日本語と記号の表示テスト（崩れて見えるならフォントかコードページの問題）:' -ForegroundColor DarkGray
Write-Host '  ✓ 日本語テスト ★ NotebookLM 連携 🎧'

# ============================================================================
# 結果の表示
# ============================================================================

Write-Host ''
Write-Host '── 診断結果 ──' -ForegroundColor DarkGray
foreach ($r in $script:Results) {
    $color = switch ($r.Status) {
        'PASS' { 'Green' }
        'FAIL' { 'Red' }
        'WARN' { 'Yellow' }
        default { 'DarkGray' }
    }
    Write-Host ('  [{0}] L{1} {2}' -f $r.Status, $r.Layer, $r.Check) -ForegroundColor $color -NoNewline
    if ($r.Detail) { Write-Host ("  {0}" -f $r.Detail) -ForegroundColor DarkGray } else { Write-Host '' }
    if ($r.Status -ne 'PASS' -and $r.Fix) {
        Write-Host ('        → {0}' -f $r.Fix) -ForegroundColor DarkGray
    }
}

$failCount = @($script:Results | Where-Object { $_.Status -eq 'FAIL' }).Count
$warnCount = @($script:Results | Where-Object { $_.Status -eq 'WARN' }).Count
Write-Host ''
Write-Host ('  FAIL {0} / WARN {1} / 合計 {2}' -f $failCount, $warnCount, $script:Results.Count)

# ============================================================================
# 修復
# ============================================================================

if (-not $Apply) {
    Write-Host ''
    if ($failCount -gt 0 -or $warnCount -gt 0) {
        Write-Host '修復するには -Apply を付けて再実行してください:' -ForegroundColor Yellow
        Write-Host '  pwsh -NoProfile -File .\scripts\fix-mojibake.ps1 -Apply'
    } else {
        Write-Host '対策は適用済みです。' -ForegroundColor Green
    }
    exit ([int]($failCount -gt 0))
}

Write-Head '修復を適用します'

# 層 1 + 3: 環境変数
foreach ($pair in @(@{ Name = 'PYTHONUTF8'; Value = '1' }, @{ Name = 'PYTHONIOENCODING'; Value = 'utf-8' })) {
    if ($Scope -eq 'User') {
        [Environment]::SetEnvironmentVariable($pair.Name, $pair.Value, 'User')
        Write-Host ('  設定（ユーザー環境変数）: {0}={1}' -f $pair.Name, $pair.Value) -ForegroundColor Green
    }
    Set-Item -Path ("Env:{0}" -f $pair.Name) -Value $pair.Value
    Write-Host ('  設定（現セッション）:     {0}={1}' -f $pair.Name, $pair.Value) -ForegroundColor Green
}

# 層 2: 現セッションのコンソール
try {
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [Console]::OutputEncoding = $utf8
    $global:OutputEncoding = $utf8
    Write-Host '  設定（現セッション）:     Console/OutputEncoding = UTF-8' -ForegroundColor Green
} catch {
    Write-Host ('  コンソールエンコーディングを変更できませんでした: {0}' -f $_.Exception.Message) -ForegroundColor Yellow
}

# 層 3: プロファイル
$profileBlock = @'

# --- NotebookLM 連携キット: UTF-8 設定 (scripts/fix-mojibake.ps1 が追記) ---
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$OutputEncoding = New-Object System.Text.UTF8Encoding $false
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$PSDefaultParameterValues['Out-File:Encoding']    = 'utf8'
$PSDefaultParameterValues['Set-Content:Encoding'] = 'utf8'
$PSDefaultParameterValues['Add-Content:Encoding'] = 'utf8'
# --- ここまで ---
'@

if ($PROFILE) {
    $profileDir = Split-Path -Parent $PROFILE
    if ($profileDir -and -not (Test-Path $profileDir)) {
        New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
    }
    if (-not (Test-Path $PROFILE)) {
        New-Item -ItemType File -Path $PROFILE -Force | Out-Null
    }
    $existing = Get-Content -Path $PROFILE -Raw -ErrorAction SilentlyContinue
    if ($existing -and $existing -match 'NotebookLM 連携キット: UTF-8 設定') {
        Write-Host '  プロファイルには既に追記済みです（変更しません）' -ForegroundColor DarkGray
    } else {
        Add-Content -Path $PROFILE -Value $profileBlock -Encoding UTF8
        Write-Host ('  追記: {0}' -f $PROFILE) -ForegroundColor Green
    }
} else {
    Write-Host '  $PROFILE が解決できないため、プロファイルへの追記をスキップしました' -ForegroundColor Yellow
}

Write-Host ''
Write-Host '修復が完了しました。' -ForegroundColor Green
Write-Host '  新しいシェルを開いてから、もう一度診断してください:'
Write-Host '    pwsh -NoProfile -File .\scripts\fix-mojibake.ps1'
Write-Host ''
Write-Host '  本スクリプトが変更しないもの（必要なら手動で）:' -ForegroundColor DarkGray
Write-Host '    - システムロケールの UTF-8 化（副作用が大きい / docs/04 §2）' -ForegroundColor DarkGray
Write-Host '    - コンソールフォント（レガシーコンソールのプロパティ / docs/04 §4）' -ForegroundColor DarkGray
