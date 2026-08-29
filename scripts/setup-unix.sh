#!/usr/bin/env bash
#
# Codex × NotebookLM 連携キット — macOS / Linux セットアップ
#
#   ./scripts/setup-unix.sh                 # 推奨構成（notebooklm-py）を導入
#   ./scripts/setup-unix.sh --with-browser  # notebooklm-mcp もフォールバックとして導入
#   ./scripts/setup-unix.sh --no-login      # 認証をスキップ（後で notebooklm login）
#   ./scripts/setup-unix.sh --dry-run       # 実行内容を表示するだけ
#
# 詳細: docs/02-setup-codex.md

set -euo pipefail

WITH_BROWSER=0
DO_LOGIN=1
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --with-browser) WITH_BROWSER=1 ;;
    --no-login)     DO_LOGIN=0 ;;
    --dry-run)      DRY_RUN=1 ;;
    -h|--help)      sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "不明なオプション: $1" >&2; exit 2 ;;
  esac
  shift
done

# --- 出力ヘルパ -------------------------------------------------------------
if [ -t 1 ]; then
  C_OK=$'\033[32m'; C_WARN=$'\033[33m'; C_ERR=$'\033[31m'; C_DIM=$'\033[2m'; C_OFF=$'\033[0m'
else
  C_OK=''; C_WARN=''; C_ERR=''; C_DIM=''; C_OFF=''
fi
info() { printf '%s==>%s %s\n' "$C_DIM" "$C_OFF" "$*"; }
ok()   { printf '%s  OK%s %s\n' "$C_OK" "$C_OFF" "$*"; }
warn() { printf '%s WARN%s %s\n' "$C_WARN" "$C_OFF" "$*"; }
die()  { printf '%s FAIL%s %s\n' "$C_ERR" "$C_OFF" "$*" >&2; exit 1; }

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '%s  [dry-run]%s %s\n' "$C_DIM" "$C_OFF" "$*"
  else
    printf '%s  $%s %s\n' "$C_DIM" "$C_OFF" "$*"
    "$@"
  fi
}

have() { command -v "$1" >/dev/null 2>&1; }

# --- 1. 前提確認 ------------------------------------------------------------
info "前提条件を確認します"

if have python3; then
  py_ver="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  if python3 -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,10) else 1)'; then
    ok "Python $py_ver"
  else
    die "Python $py_ver は非対応です。3.10 以上が必要です。"
  fi
else
  die "python3 が見つかりません。Python 3.10+ を導入してください。"
fi

if have uv; then
  ok "uv $(uv --version 2>/dev/null | awk '{print $2}')"
else
  warn "uv が見つかりません。次のいずれかで導入してください:"
  echo "      curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "      brew install uv"
  die "uv の導入後にもう一度実行してください。"
fi

if [ "$WITH_BROWSER" -eq 1 ]; then
  have node || die "--with-browser には Node.js 18+ が必要です。"
  node_major="$(node -p 'process.versions.node.split(".")[0]')"
  [ "$node_major" -ge 18 ] || die "Node.js $node_major は非対応です。18 以上が必要です。"
  ok "Node.js $(node -v)"
fi

AGENT_CLI=""
if have codex; then AGENT_CLI="codex"; ok "Codex CLI を検出"; fi
if have claude; then
  ok "Claude Code を検出"
  [ -z "$AGENT_CLI" ] && AGENT_CLI="claude"
fi
[ -n "$AGENT_CLI" ] || warn "codex / claude のどちらも見つかりません。MCP 登録は手動で行ってください。"

# --- 2. notebooklm-py の導入 -----------------------------------------------
info "notebooklm-py を導入します"
if have notebooklm && [ "$DRY_RUN" -eq 0 ]; then
  ok "既に導入済み: $(command -v notebooklm)"
  info "更新する場合: uv tool upgrade notebooklm-py"
else
  run uv tool install "notebooklm-py[browser,mcp]"
fi

# --- 3. 認証 ----------------------------------------------------------------
if [ "$DO_LOGIN" -eq 1 ]; then
  info "Google 認証の状態を確認します"
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '%s  [dry-run]%s notebooklm auth check --test --json\n' "$C_DIM" "$C_OFF"
  elif notebooklm auth check --test --json >/dev/null 2>&1; then
    ok "認証済みです"
  else
    warn "未認証です。ブラウザが開くので Google にサインインしてください。"
    if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] || [ "$(uname -s)" = "Darwin" ]; then
      run notebooklm login
    else
      warn "ディスプレイが検出できません。ヘッドレス環境向けの選択肢:"
      echo "      notebooklm login --browser-cookies firefox"
      echo "      notebooklm login --master-token --account you@example.com"
      echo "      （GUI のあるマシンでログインし ~/.notebooklm/ を持ち込む）"
      echo "      詳細: docs/02-setup-codex.md#7-ヘッドレス--サーバー運用"
    fi
  fi
else
  info "認証はスキップしました（後で: notebooklm login）"
fi

# --- 4. notebooklm-mcp（任意） ---------------------------------------------
if [ "$WITH_BROWSER" -eq 1 ]; then
  info "notebooklm-mcp（フォールバック構成）を準備します"
  run npx --yes notebooklm-mcp@latest --version || \
    warn "バージョン確認に失敗しました。初回は npx が依存を取得するため時間がかかります。"
  info "初回ログインは、クライアントから setup_auth ツールを呼んで行います。"
fi

# --- 5. MCP 登録 ------------------------------------------------------------
info "エージェントに MCP サーバーを登録します"

if have codex; then
  if [ "$DRY_RUN" -eq 0 ] && codex mcp list 2>/dev/null | grep -q '^notebooklm\b'; then
    ok "codex: notebooklm は登録済み"
  else
    run codex mcp add notebooklm -- uvx --from "notebooklm-py[mcp]" notebooklm-mcp
  fi
  if [ "$WITH_BROWSER" -eq 1 ]; then
    run codex mcp add notebooklm-browser -- npx notebooklm-mcp@latest
  fi
  warn "~/.codex/config.toml に startup_timeout_sec / tool_timeout_sec の追記を推奨します。"
  echo "      雛形: config/codex.config.toml.example"
fi

if have claude; then
  if [ "$DRY_RUN" -eq 0 ]; then
    notebooklm mcp install claude-code || warn "claude-code への自動設定に失敗しました。"
  else
    printf '%s  [dry-run]%s notebooklm mcp install claude-code\n' "$C_DIM" "$C_OFF"
  fi
  if [ "$WITH_BROWSER" -eq 1 ]; then
    run claude mcp add notebooklm-browser -- npx notebooklm-mcp@latest
  fi
fi

# --- 6. 次のステップ --------------------------------------------------------
cat <<'EOS'

────────────────────────────────────────────────
セットアップが完了しました。

  1. 検証:      ./scripts/verify-unix.sh
  2. 動作確認:  notebooklm create "Setup Smoke Test"
                notebooklm ask "テストです" --notebook <id> --json
  3. クライアントを再起動してから MCP ツールを使ってください。

  ドキュメント:
    セットアップ詳細    docs/02-setup-codex.md
    ツール選定の根拠    docs/03-comparison.md
    プロンプト集        docs/05-prompt-templates.md
    困ったとき          docs/07-troubleshooting.md
────────────────────────────────────────────────
EOS
