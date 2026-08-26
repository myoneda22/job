#!/usr/bin/env bash
#
# codex-chatgpt のインストーラ。
#
#   ./install.sh                 # ~/.codex/chatgpt.config.toml を配置
#   ./install.sh --link ~/bin    # ラッパーへの symlink も作る
#   ./install.sh --profile work  # 別名のプロファイルとして入れる
#
# やること:
#   1. codex CLI と、そのバージョンが `-p` (profile v2) に対応しているか確認
#   2. chatgpt.config.toml を $CODEX_HOME/<profile>.config.toml へコピー
#   3. 置いた設定を codex 自身に読ませて構文検証
#   4. API キーで保存済みの auth.json があればバックアップして注意を出す

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_TOML="$SCRIPT_DIR/chatgpt.config.toml"
WRAPPER="$SCRIPT_DIR/bin/codex-chatgpt"

CODEX_BIN="${CODEX_BIN:-codex}"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
PROFILE="${CODEX_CHATGPT_PROFILE:-chatgpt}"
LINK_DIR=""

die() {
  printf 'install.sh: %s\n' "$*" >&2
  exit 1
}
info() { printf '  %s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }

usage() {
  sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 0
}

while [ $# -gt 0 ]; do
  case "$1" in
    --profile)     PROFILE="${2:?--profile に名前が必要です}"; shift 2 ;;
    --codex-home)  CODEX_HOME="${2:?--codex-home にパスが必要です}"; shift 2 ;;
    --link)        LINK_DIR="${2:?--link にディレクトリが必要です}"; shift 2 ;;
    -h | --help)   usage ;;
    *)             die "不明な引数: $1 (--help を参照)" ;;
  esac
done

PROFILE_FILE="$CODEX_HOME/$PROFILE.config.toml"
export CODEX_HOME

step "codex CLI を確認"
command -v "$CODEX_BIN" >/dev/null 2>&1 ||
  die "codex が見つかりません。'npm install -g @openai/codex' を実行してください。"
info "$("$CODEX_BIN" --version 2>&1 | head -1) ($(command -v "$CODEX_BIN"))"

# profile v2 = 「-p <name> で $CODEX_HOME/<name>.config.toml を重ねる」方式。
# 古い codex の -p は config.toml 内の [profiles.<name>] を指すので、
# この設定ファイルの置き方では効かない。
if ! "$CODEX_BIN" --help 2>&1 | grep -q 'CONFIG_PROFILE_V2'; then
  die "この codex は -p のファイル方式 (profile v2) に対応していません。
    'npm install -g @openai/codex@latest' で更新してください。"
fi
info "-p (profile v2) 対応を確認"

step "プロファイルを配置: $PROFILE_FILE"
[ -f "$SOURCE_TOML" ] || die "$SOURCE_TOML がありません"
mkdir -p "$CODEX_HOME"
if [ -e "$PROFILE_FILE" ]; then
  backup="$PROFILE_FILE.bak-$(date +%Y%m%d%H%M%S)"
  cp -p "$PROFILE_FILE" "$backup"
  info "既存ファイルを退避: $backup"
fi
cp "$SOURCE_TOML" "$PROFILE_FILE"
info "配置しました"

step "設定を検証"
# 実際に codex に読ませる。--strict-config で未知のキーを弾くので、
# forced_login_method をこの codex が知らなければここで落ちる。
# resume --last は入力なしで即エラー終了するため、API 呼び出しは発生しない。
validation="$("$CODEX_BIN" exec -p "$PROFILE" --strict-config resume --last \
  --skip-git-repo-check </dev/null 2>&1 || true)"
if printf '%s' "$validation" | grep -qi 'Error loading config'; then
  printf '%s\n' "$validation" >&2
  die "codex が $PROFILE_FILE を受け付けませんでした"
fi
info "codex が設定を受け付けました"

step "保存済みの認証情報を確認"
AUTH_FILE="$CODEX_HOME/auth.json"
if [ -f "$AUTH_FILE" ] && grep -q '"apikey"' "$AUTH_FILE"; then
  backup="$AUTH_FILE.apikey.bak-$(date +%Y%m%d%H%M%S)"
  cp -p "$AUTH_FILE" "$backup"
  info "API キーでログイン済みです。'codex -p $PROFILE' はこれを破棄して"
  info "ChatGPT ログインを要求します。念のため退避しました: $backup"
else
  info "API キーの保存は見つかりませんでした"
fi

if [ -n "$LINK_DIR" ]; then
  step "ラッパーを symlink: $LINK_DIR/codex-chatgpt"
  mkdir -p "$LINK_DIR"
  ln -sf "$WRAPPER" "$LINK_DIR/codex-chatgpt"
  info "作成しました (PATH に $LINK_DIR を通してください)"
fi

cat <<EOF

完了しました。次の手順:

  1. ChatGPT アカウントでログイン
       $WRAPPER login
     ブラウザを開けない環境 (SSH / コンテナ) の場合:
       $WRAPPER login --device-auth

  2. 状態を確認
       $WRAPPER login status

  3. 使う
       $WRAPPER                     # 対話 TUI
       $WRAPPER exec "テストを直して"   # ヘッドレス

  ラッパーを使わず素の codex を叩く場合は -p $PROFILE を必ず付けてください:
       codex -p $PROFILE exec "..."
EOF
