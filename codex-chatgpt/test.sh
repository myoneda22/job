#!/usr/bin/env bash
#
# codex-chatgpt のテスト。
# 偽の codex をスタブとして PATH に置き、install.sh とラッパーの挙動を確認する。
# PATH に本物の codex があれば、最後にオフラインの結合テストも走る。
#
#   ./test.sh

set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALL="$SCRIPT_DIR/install.sh"
WRAPPER="$SCRIPT_DIR/bin/codex-chatgpt"
REAL_CODEX="$(command -v codex 2>/dev/null || true)"

pass=0
fail=0

ok()   { printf '  ok   %s\n' "$1"; pass=$((pass + 1)); }
notok() {
  printf '  FAIL %s\n' "$1"
  [ $# -gt 1 ] && printf '       %s\n' "$2"
  fail=$((fail + 1))
}
check_contains() {
  local name="$1" haystack="$2" needle="$3"
  case "$haystack" in
    *"$needle"*) ok "$name" ;;
    *) notok "$name" "期待した文字列がありません: $needle" ;;
  esac
}
check_not_contains() {
  local name="$1" haystack="$2" needle="$3"
  case "$haystack" in
    *"$needle"*) notok "$name" "含まれてはいけない文字列: $needle" ;;
    *) ok "$name" ;;
  esac
}

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# --- codex スタブ ---------------------------------------------------------
mkdir -p "$WORK/bin"
cat > "$WORK/bin/codex" <<'STUB'
#!/usr/bin/env bash
case "${1-}" in
  --version) echo "codex-cli 0.149.1-stub"; exit 0 ;;
  --help)
    echo "  -p, --profile <CONFIG_PROFILE_V2>"
    echo "          Layer \$CODEX_HOME/<name>.config.toml on top of the base user config"
    exit 0 ;;
esac
: > "${CODEX_STUB_ARGV:-/dev/null}"
for arg in "$@"; do printf '%s\n' "$arg" >> "${CODEX_STUB_ARGV:-/dev/null}"; done
{
  printf 'OPENAI_API_KEY=%s\n' "${OPENAI_API_KEY-<unset>}"
  printf 'CODEX_API_KEY=%s\n' "${CODEX_API_KEY-<unset>}"
  printf 'CODEX_HOME=%s\n' "${CODEX_HOME-<unset>}"
} > "${CODEX_STUB_ENV:-/dev/null}"
printf '%s\n' "${CODEX_STUB_OUTPUT:-stub ok}"
exit "${CODEX_STUB_RC:-0}"
STUB
chmod +x "$WORK/bin/codex"

# profile v2 を知らない古い codex のスタブ
mkdir -p "$WORK/oldbin"
cat > "$WORK/oldbin/codex" <<'STUB'
#!/usr/bin/env bash
case "${1-}" in
  --version) echo "codex-cli 0.20.0-stub"; exit 0 ;;
  --help)    echo "  -p, --profile <CONFIG_PROFILE>"; exit 0 ;;
esac
exit 0
STUB
chmod +x "$WORK/oldbin/codex"

export PATH="$WORK/bin:$PATH"
export CODEX_STUB_ARGV="$WORK/argv.txt"
export CODEX_STUB_ENV="$WORK/env.txt"

# --- install.sh -----------------------------------------------------------
echo "install.sh"

HOME_A="$WORK/home-a"
out="$(CODEX_HOME="$HOME_A" "$INSTALL" 2>&1)"
rc=$?
[ $rc -eq 0 ] && ok "正常終了する" || notok "正常終了する" "rc=$rc: $out"
[ -f "$HOME_A/chatgpt.config.toml" ] &&
  ok "プロファイルを配置する" || notok "プロファイルを配置する"
check_contains "配置した中身に forced_login_method がある" \
  "$(cat "$HOME_A/chatgpt.config.toml" 2>/dev/null)" 'forced_login_method = "chatgpt"'
check_contains "検証で --strict-config を渡す" "$(cat "$CODEX_STUB_ARGV")" "--strict-config"
check_contains "検証で -p を渡す" "$(cat "$CODEX_STUB_ARGV")" "-p"

out="$(CODEX_HOME="$HOME_A" "$INSTALL" 2>&1)"
ls "$HOME_A"/chatgpt.config.toml.bak-* >/dev/null 2>&1 &&
  ok "既存プロファイルを退避する" || notok "既存プロファイルを退避する" "$out"

HOME_B="$WORK/home-b"
mkdir -p "$HOME_B"
printf '{\n  "auth_mode": "apikey",\n  "OPENAI_API_KEY": "sk-test"\n}\n' > "$HOME_B/auth.json"
out="$(CODEX_HOME="$HOME_B" "$INSTALL" 2>&1)"
ls "$HOME_B"/auth.json.apikey.bak-* >/dev/null 2>&1 &&
  ok "API キーの auth.json を退避する" || notok "API キーの auth.json を退避する" "$out"
check_contains "破棄される旨を警告する" "$out" "破棄"

HOME_C="$WORK/home-c"
out="$(CODEX_HOME="$HOME_C" PATH="$WORK/oldbin:$PATH" "$INSTALL" 2>&1)"
rc=$?
[ $rc -ne 0 ] && ok "profile v2 非対応の codex では失敗する" ||
  notok "profile v2 非対応の codex では失敗する" "$out"

HOME_D="$WORK/home-d"
out="$(CODEX_HOME="$HOME_D" CODEX_STUB_OUTPUT="Error loading config.toml: unknown field" \
  "$INSTALL" 2>&1)"
rc=$?
[ $rc -ne 0 ] && ok "codex が設定を拒否したら失敗する" ||
  notok "codex が設定を拒否したら失敗する" "$out"

HOME_E="$WORK/home-e"
out="$(CODEX_HOME="$HOME_E" "$INSTALL" --profile work --link "$WORK/linkdir" 2>&1)"
[ -f "$HOME_E/work.config.toml" ] &&
  ok "--profile で名前を変えられる" || notok "--profile で名前を変えられる" "$out"
[ -L "$WORK/linkdir/codex-chatgpt" ] &&
  ok "--link で symlink を作る" || notok "--link で symlink を作る" "$out"

# --- ラッパー -------------------------------------------------------------
echo
echo "bin/codex-chatgpt"

HOME_W="$WORK/home-w"
mkdir -p "$HOME_W"

out="$(CODEX_HOME="$HOME_W" "$WRAPPER" exec "hi" 2>&1)"
rc=$?
[ $rc -ne 0 ] && ok "プロファイルが無ければ失敗する" || notok "プロファイルが無ければ失敗する"
check_contains "プロファイルの場所を教える" "$out" "$HOME_W/chatgpt.config.toml"

cp "$SCRIPT_DIR/chatgpt.config.toml" "$HOME_W/chatgpt.config.toml"

CODEX_HOME="$HOME_W" "$WRAPPER" exec "hi" >/dev/null 2>&1
argv="$(cat "$CODEX_STUB_ARGV")"
check_contains "-p を付けて呼ぶ" "$argv" "-p"
check_contains "プロファイル名を渡す" "$argv" "chatgpt"
check_contains "引数をそのまま渡す" "$argv" "exec"
[ "$(head -1 "$CODEX_STUB_ARGV")" = "-p" ] &&
  ok "-p をサブコマンドより前に置く" || notok "-p をサブコマンドより前に置く" "$argv"

CODEX_HOME="$HOME_W" OPENAI_API_KEY=sk-a CODEX_API_KEY=sk-b \
  "$WRAPPER" exec "hi" >/dev/null 2>&1
env_seen="$(cat "$CODEX_STUB_ENV")"
check_contains "OPENAI_API_KEY を外す" "$env_seen" "OPENAI_API_KEY=<unset>"
check_contains "CODEX_API_KEY を外す" "$env_seen" "CODEX_API_KEY=<unset>"
check_not_contains "キーの値を渡さない" "$env_seen" "sk-a"

out="$(CODEX_HOME="$HOME_W" OPENAI_API_KEY=sk-a "$WRAPPER" exec "hi" 2>&1)"
check_contains "キーを無視した旨を伝える" "$out" "無視"

CODEX_HOME="$HOME_W" "$WRAPPER" login >/dev/null 2>&1
argv="$(cat "$CODEX_STUB_ARGV")"
check_contains "login をそのまま渡す" "$argv" "login"
check_contains "login では -c で強制する" "$argv" 'forced_login_method="chatgpt"'
check_not_contains "login に -p を渡さない" "$argv" "-p"

CODEX_HOME="$HOME_W" "$WRAPPER" login status >/dev/null 2>&1
check_contains "login status を渡せる" "$(cat "$CODEX_STUB_ARGV")" "status"

CODEX_HOME="$HOME_W" "$WRAPPER" logout >/dev/null 2>&1
argv="$(cat "$CODEX_STUB_ARGV")"
check_contains "logout をそのまま渡す" "$argv" "logout"
check_contains "logout でも -c で強制する" "$argv" 'forced_login_method="chatgpt"'

CODEX_HOME="$HOME_W" "$WRAPPER" >/dev/null 2>&1
check_contains "引数なしなら TUI (-p のみ)" "$(cat "$CODEX_STUB_ARGV")" "-p"

# --- 本物の codex での結合テスト (オフライン) ------------------------------
echo
if [ -n "$REAL_CODEX" ]; then
  echo "結合テスト (本物の codex: $REAL_CODEX)"
  HOME_R="$WORK/home-real"
  out="$(PATH="${PATH#"$WORK/bin:"}" CODEX_HOME="$HOME_R" "$INSTALL" 2>&1)"
  rc=$?
  [ $rc -eq 0 ] && ok "本物の codex が設定を受け付ける" ||
    notok "本物の codex が設定を受け付ける" "$out"
else
  echo "結合テスト: codex が PATH に無いのでスキップ"
fi

echo
printf '%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
