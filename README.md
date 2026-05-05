# ollama launch claude-desktop

A small shell script that starts [Ollama](https://ollama.com) (if it isn't already running), ensures a local model is available, then launches [Claude Desktop](https://claude.ai/download).

## Requirements

- [Ollama](https://ollama.com) installed and in `PATH`
- [Claude Desktop](https://claude.ai/download) installed

## Usage

```sh
./launch.sh launch claude-desktop
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `-m MODEL` / `--model MODEL` | `llama3` | Ollama model to pull/verify before launch |
| `-h` / `--help` | — | Print usage |

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama server address |
| `OLLAMA_MODEL` | `llama3` | Model used when `-m` is not set |

### Examples

```sh
# Default model (llama3)
./launch.sh launch claude-desktop

# Use a different model
./launch.sh --model mistral launch claude-desktop

# Override via env
OLLAMA_MODEL=gemma3 ./launch.sh launch claude-desktop
```

## What it does

1. Checks whether Ollama is already serving on `OLLAMA_HOST`.
2. If not, runs `ollama serve` in the background and waits up to 10 s for it to become ready.
3. Checks whether the requested model is already pulled; pulls it if missing.
4. Searches well-known paths for the Claude Desktop binary and execs it.
