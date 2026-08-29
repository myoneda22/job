#!/usr/bin/env bash
#
# Codex × NotebookLM 連携キット — 導入検証（macOS / Linux）
#
#   ./scripts/verify-unix.sh          # 読み取り専用のチェックのみ
#   ./scripts/verify-unix.sh --live   # 実際にノートブックを作って疎通確認（要認証・API を消費）
#
# 終了コード: 0 = 全て合格 / 1 = 失敗あり
# 詳細: docs/07-troubleshooting.md

set -uo pipefail

LIVE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --live)    LIVE=1 ;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "不明なオプション: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ -t 1 ]; then
  C_OK=$'\033[32m'; C_WARN=$'\033[33m'; C_ERR=$'\033[31m'; C_DIM=$'\033[2m'; C_OFF=$'\033[0m'
else
  C_OK=''; C_WARN=''; C_ERR=''; C_DIM=''; C_OFF=''
fi

PASS=0; FAIL=0; SKIP=0
pass() { PASS=$((PASS+1)); printf '%s PASS %s %s\n' "$C_OK"   "$C_OFF" "$*"; }
fail() { FAIL=$((FAIL+1)); printf '%s FAIL %s %s\n' "$C_ERR"  "$C_OFF" "$*"; }
skip() { SKIP=$((SKIP+1)); printf '%s SKIP %s %s\n' "$C_WARN" "$C_OFF" "$*"; }
hint() { printf '%s      → %s%s\n' "$C_DIM" "$*" "$C_OFF"; }
section() { printf '\n%s── %s ──%s\n' "$C_DIM" "$*" "$C_OFF"; }

have() { command -v "$1" >/dev/null 2>&1; }

# --- 1. ランタイム ----------------------------------------------------------
section "ランタイム"

if have python3 && python3 -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,10) else 1)'; then
  pass "Python $(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"
else
  fail "Python 3.10+ が必要です"
fi

if have uv; then pass "uv ($(command -v uv))"; else skip "uv が未導入（pipx / venv でも可）"; fi

if have node; then
  node_major="$(node -p 'process.versions.node.split(".")[0]')"
  if [ "$node_major" -ge 18 ]; then pass "Node.js $(node -v)"; else fail "Node.js 18+ が必要です（現在 $(node -v)）"; fi
else
  skip "Node.js 未導入（notebooklm-mcp を使わないなら不要）"
fi

# --- 2. notebooklm-py -------------------------------------------------------
section "notebooklm-py"

if have notebooklm; then
  pass "notebooklm CLI: $(command -v notebooklm)"
else
  fail "notebooklm コマンドが見つかりません"
  hint "uv tool install \"notebooklm-py[browser,mcp]\""
fi

if have notebooklm-mcp; then
  resolved="$(command -v notebooklm-mcp)"
  case "$resolved" in
    *node_modules*|*/npm/*) skip "notebooklm-mcp は npm 版が優先されています: $resolved"
                            hint "MCP 登録では uvx --from \"notebooklm-py[mcp]\" notebooklm-mcp と明示してください" ;;
    *) pass "notebooklm-mcp（Python 版）: $resolved" ;;
  esac
else
  skip "notebooklm-mcp コマンドなし（MCP extra 未導入。CLI 直叩き運用なら不要）"
fi

# --- 3. 認証 ----------------------------------------------------------------
section "認証"

if have notebooklm; then
  if auth_out="$(notebooklm auth check --test --json 2>&1)"; then
    if printf '%s' "$auth_out" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
      pass "Google 認証 OK"
    else
      fail "auth check は成功したが status が ok ではありません"
      printf '%s      %s%s\n' "$C_DIM" "$(printf '%s' "$auth_out" | head -c 300)" "$C_OFF"
    fi
  else
    fail "未認証、またはセッション切れ"
    hint "notebooklm login"
    hint "Windows で Cookie 復号に失敗する場合: docs/07-troubleshooting.md#windows-認証が通らない"
  fi
else
  skip "notebooklm 未導入のため認証チェックをスキップ"
fi

# --- 4. エンコーディング ----------------------------------------------------
section "エンコーディング"

enc="$(python3 -c 'import sys; print(sys.stdout.encoding or "")' 2>/dev/null | tr 'A-Z' 'a-z')"
case "$enc" in
  utf-8|utf8) pass "Python stdout: $enc" ;;
  "")         skip "Python stdout エンコーディングを判定できません" ;;
  *)          fail "Python stdout が $enc です（UTF-8 ではありません）"
              hint "export PYTHONUTF8=1 / docs/04-windows-encoding.md" ;;
esac

if python3 -c 'print("✓ 日本語 ★ 🎧")' >/dev/null 2>&1; then
  pass "非 ASCII の出力に成功"
else
  fail "非 ASCII を出力できません（文字化け対策が必要）"
  hint "docs/04-windows-encoding.md"
fi

# --- 5. MCP 登録 ------------------------------------------------------------
section "MCP 登録"

if have codex; then
  if codex mcp list 2>/dev/null | grep -q 'notebooklm'; then
    pass "Codex に notebooklm 系サーバーが登録済み"
    codex mcp list 2>/dev/null | grep 'notebooklm' | sed "s/^/${C_DIM}      /;s/$/${C_OFF}/"
  else
    fail "Codex に notebooklm が登録されていません"
    hint "codex mcp add notebooklm -- uvx --from \"notebooklm-py[mcp]\" notebooklm-mcp"
  fi
else
  skip "Codex CLI 未導入"
fi

if have claude; then
  if claude mcp list 2>/dev/null | grep -q 'notebooklm'; then
    pass "Claude Code に notebooklm 系サーバーが登録済み"
  else
    fail "Claude Code に notebooklm が登録されていません"
    hint "notebooklm mcp install claude-code"
  fi
else
  skip "Claude Code 未導入"
fi

# --- 6. 疎通確認（--live のみ） --------------------------------------------
section "疎通確認"

if [ "$LIVE" -eq 0 ]; then
  skip "--live を付けると実際にノートブックを作成して確認します（API クォータを消費）"
elif ! have notebooklm; then
  skip "notebooklm 未導入"
else
  nb_name="verify-$(date +%Y%m%d-%H%M%S)"
  if create_out="$(notebooklm create "$nb_name" --json 2>&1)"; then
    pass "ノートブック作成: $nb_name"
    printf '%s      %s%s\n' "$C_DIM" "$(printf '%s' "$create_out" | head -c 200)" "$C_OFF"
    printf '%s      作成したノートブックは NotebookLM 側に残ります。不要なら削除してください。%s\n' "$C_DIM" "$C_OFF"
  else
    fail "ノートブックを作成できません"
    printf '%s      %s%s\n' "$C_DIM" "$(printf '%s' "$create_out" | head -c 300)" "$C_OFF"
    hint "レート制限の可能性: docs/07-troubleshooting.md#レート制限"
  fi
fi

# --- 結果 -------------------------------------------------------------------
printf '\n%s────────────────────────%s\n' "$C_DIM" "$C_OFF"
printf '  PASS %d / FAIL %d / SKIP %d\n' "$PASS" "$FAIL" "$SKIP"
if [ "$FAIL" -eq 0 ]; then
  printf '%s  すべてのチェックに合格しました。%s\n' "$C_OK" "$C_OFF"
  exit 0
else
  printf '%s  失敗があります。docs/07-troubleshooting.md を参照してください。%s\n' "$C_ERR" "$C_OFF"
  exit 1
fi
