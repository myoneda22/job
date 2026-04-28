# terminal-setup

Dotfiles and a one-shot setup script for a productive terminal development environment.

## What's included

| File | Destination | Description |
|---|---|---|
| `config/zshrc` | `~/.zshrc` | Zsh + Oh My Zsh, plugins, aliases, fzf |
| `config/bashrc` | `~/.bashrc` | Bash fallback with matching aliases |
| `config/tmux.conf` | `~/.tmux.conf` | tmux with Catppuccin colours, vim keys |
| `config/gitconfig` | `~/.gitconfig` | Git aliases, delta diff, sensible defaults |

### Installed tools (via `setup.sh`)

`git` · `curl` · `wget` · `zsh` · `tmux` · `vim` · `fzf` · `ripgrep` · `bat` · `tree` · `jq` · `gh`

Oh My Zsh plugins: `zsh-autosuggestions`, `zsh-syntax-highlighting`, plus the built-in `git z fzf docker kubectl`.

## Quick start

```bash
git clone https://github.com/myoneda22/job.git ~/terminal-setup
cd ~/terminal-setup
chmod +x setup.sh
./setup.sh
```

`setup.sh` will:
1. Install packages (Homebrew on macOS, apt on Debian/Ubuntu).
2. Install Oh My Zsh and the two community plugins.
3. Symlink every config file, backing up existing files to `<file>.bak`.
4. Set zsh as the default shell.

Restart your terminal afterwards, or run `exec zsh`.

## Local overrides

Machine-specific settings that should not be committed go in:

- `~/.zshrc.local` — sourced at the end of `.zshrc`
- `~/.bashrc.local` — sourced at the end of `.bashrc`

## tmux key reference

| Key | Action |
|---|---|
| `C-a` | Prefix |
| `Prefix \|` | Split horizontally |
| `Prefix -` | Split vertically |
| `Prefix h/j/k/l` | Navigate panes |
| `Prefix H/J/K/L` | Resize panes |
| `M-←/→` | Previous/next window (no prefix) |
| `Prefix r` | Reload config |
| `Prefix Enter` | Enter copy mode (vi keys) |
