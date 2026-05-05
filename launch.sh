#!/usr/bin/env bash
set -euo pipefail

CLAUDE_DESKTOP_PATHS=(
  "$HOME/Applications/Claude.app/Contents/MacOS/Claude"
  "/Applications/Claude.app/Contents/MacOS/Claude"
  "/usr/bin/claude-desktop"
  "/usr/local/bin/claude-desktop"
  "$HOME/.local/bin/claude-desktop"
)

OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
MODEL="${OLLAMA_MODEL:-llama3}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS] <command> <target>

Commands:
  launch claude-desktop    Start Ollama (if not running) and launch Claude Desktop

Options:
  -m, --model MODEL    Ollama model to ensure is available (default: $MODEL)
  -h, --help           Show this help message

Environment:
  OLLAMA_HOST          Ollama server URL (default: $OLLAMA_HOST)
  OLLAMA_MODEL         Model to use (default: $MODEL)

Examples:
  $(basename "$0") launch claude-desktop
  $(basename "$0") --model mistral launch claude-desktop
EOF
}

log() { printf '[%s] %s\n' "$(date +%T)" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

ollama_running() {
  curl -sf "$OLLAMA_HOST/api/tags" > /dev/null 2>&1
}

start_ollama() {
  if ollama_running; then
    log "Ollama already running at $OLLAMA_HOST"
    return
  fi

  if ! command -v ollama &> /dev/null; then
    die "ollama not found in PATH. Install from https://ollama.com"
  fi

  log "Starting Ollama..."
  ollama serve &>/tmp/ollama.log &
  local pid=$!

  local tries=0
  while ! ollama_running; do
    ((tries++)) || true
    if (( tries > 20 )); then
      kill "$pid" 2>/dev/null || true
      die "Ollama failed to start. See /tmp/ollama.log"
    fi
    sleep 0.5
  done
  log "Ollama started (pid $pid)"
}

ensure_model() {
  local model="$1"
  log "Checking model '$model'..."
  if ollama list 2>/dev/null | grep -q "^${model}"; then
    log "Model '$model' available"
    return
  fi
  log "Pulling model '$model' (this may take a while)..."
  ollama pull "$model"
}

find_claude_desktop() {
  for path in "${CLAUDE_DESKTOP_PATHS[@]}"; do
    if [[ -x "$path" ]]; then
      echo "$path"
      return
    fi
  done

  if command -v claude-desktop &>/dev/null; then
    command -v claude-desktop
    return
  fi

  return 1
}

launch_claude_desktop() {
  local binary
  if ! binary=$(find_claude_desktop); then
    die "Claude Desktop not found. Install from https://claude.ai/download"
  fi
  log "Launching Claude Desktop: $binary"
  exec "$binary" "$@"
}

cmd_launch() {
  local target="${1:-}"
  shift || true

  case "$target" in
    claude-desktop)
      start_ollama
      ensure_model "$MODEL"
      launch_claude_desktop "$@"
      ;;
    "")
      die "Missing target. Usage: launch claude-desktop"
      ;;
    *)
      die "Unknown launch target '$target'. Supported: claude-desktop"
      ;;
  esac
}

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -m|--model) MODEL="$2"; shift 2 ;;
      -h|--help)  usage; exit 0 ;;
      launch)     shift; cmd_launch "$@"; exit 0 ;;
      *)          die "Unknown argument '$1'. Use --help for usage." ;;
    esac
  done
  usage
  exit 1
}

main "$@"
