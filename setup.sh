#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/config"

log()  { echo "[setup] $*"; }
warn() { echo "[setup] WARNING: $*" >&2; }

# ── OS detection ────────────────────────────────────────────────────────────
OS="$(uname -s)"
is_mac()   { [[ "$OS" == "Darwin" ]]; }
is_linux() { [[ "$OS" == "Linux" ]]; }

# ── Package manager bootstrap ────────────────────────────────────────────────
install_brew() {
  if ! command -v brew &>/dev/null; then
    log "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  fi
}

install_apt_packages() {
  local pkgs=(git curl wget unzip zsh tmux vim fzf ripgrep bat tree jq gh)
  log "Installing apt packages: ${pkgs[*]}"
  sudo apt-get update -q
  sudo apt-get install -y "${pkgs[@]}"
}

install_brew_packages() {
  local pkgs=(git curl wget zsh tmux vim fzf ripgrep bat tree jq gh)
  log "Installing Homebrew packages: ${pkgs[*]}"
  brew install "${pkgs[@]}"
}

install_packages() {
  if is_mac; then
    install_brew
    install_brew_packages
  elif is_linux; then
    if command -v apt-get &>/dev/null; then
      install_apt_packages
    else
      warn "Unsupported Linux distro — install packages manually: git curl wget zsh tmux fzf ripgrep bat tree jq gh"
    fi
  fi
}

# ── Oh My Zsh ────────────────────────────────────────────────────────────────
install_oh_my_zsh() {
  if [[ ! -d "$HOME/.oh-my-zsh" ]]; then
    log "Installing Oh My Zsh..."
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended
  else
    log "Oh My Zsh already installed"
  fi
}

# ── zsh-autosuggestions & zsh-syntax-highlighting ────────────────────────────
install_zsh_plugins() {
  local plugin_dir="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins"
  if [[ ! -d "$plugin_dir/zsh-autosuggestions" ]]; then
    log "Installing zsh-autosuggestions..."
    git clone --depth=1 https://github.com/zsh-users/zsh-autosuggestions \
      "$plugin_dir/zsh-autosuggestions"
  fi
  if [[ ! -d "$plugin_dir/zsh-syntax-highlighting" ]]; then
    log "Installing zsh-syntax-highlighting..."
    git clone --depth=1 https://github.com/zsh-users/zsh-syntax-highlighting \
      "$plugin_dir/zsh-syntax-highlighting"
  fi
}

# ── Dotfile linking ──────────────────────────────────────────────────────────
link() {
  local src="$1" dst="$2"
  if [[ -e "$dst" && ! -L "$dst" ]]; then
    log "Backing up existing $dst → ${dst}.bak"
    mv "$dst" "${dst}.bak"
  fi
  ln -sfn "$src" "$dst"
  log "Linked $src → $dst"
}

link_dotfiles() {
  link "$DOTFILES_DIR/zshrc"     "$HOME/.zshrc"
  link "$DOTFILES_DIR/bashrc"    "$HOME/.bashrc"
  link "$DOTFILES_DIR/tmux.conf" "$HOME/.tmux.conf"

  # Only link gitconfig if it doesn't already exist
  if [[ ! -e "$HOME/.gitconfig" ]]; then
    link "$DOTFILES_DIR/gitconfig" "$HOME/.gitconfig"
  else
    log "~/.gitconfig already exists — skipping (edit $DOTFILES_DIR/gitconfig manually)"
  fi
}

# ── Default shell ────────────────────────────────────────────────────────────
set_zsh_default() {
  if [[ "$SHELL" != *"zsh"* ]]; then
    local zsh_path
    zsh_path="$(command -v zsh)"
    if ! grep -qxF "$zsh_path" /etc/shells; then
      echo "$zsh_path" | sudo tee -a /etc/shells
    fi
    log "Setting default shell to zsh..."
    chsh -s "$zsh_path"
  else
    log "zsh is already the default shell"
  fi
}

# ── Entry point ──────────────────────────────────────────────────────────────
main() {
  log "Starting terminal setup (OS: $OS)"

  install_packages
  install_oh_my_zsh
  install_zsh_plugins
  link_dotfiles
  set_zsh_default

  log "Done! Restart your terminal or run: exec zsh"
}

main "$@"
