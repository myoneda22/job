# Claude Remote Control

HTTP server for remotely controlling a Claude agent via the [`claude-code-sdk`](https://pypi.org/project/claude-code-sdk/).

Callers POST a prompt; the server runs it through the Claude agent (with full tool access) and returns the response. Sessions are resumable by passing back the `session_id`.

## Setup

```bash
pip install -e ".[dev]"
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY and API_KEY
```

## Configuration

| Env var | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(required)* | Anthropic API key |
| `API_KEY` | `changeme` | Bearer token clients must send |
| `PORT` | `8080` | Listening port |
| `HOST` | `0.0.0.0` | Listening host |
| `MAX_TURNS` | `10` | Max agentic turns per request |
| `MODEL` | `claude-sonnet-4-6` | Claude model |
| `PERMISSION_MODE` | `bypassPermissions` | `default`, `acceptEdits`, `plan`, `bypassPermissions` |

## Running

```bash
python -m claude_remote.main
```

## API

### `POST /v1/commands`

```
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

Request:
```json
{
  "prompt": "Summarize the current git log",
  "session_id": null,
  "system_prompt": null,
  "max_turns": 5
}
```

Response:
```json
{
  "session_id": "abc123-...",
  "response": "The git log shows...",
  "cost_usd": 0.0023,
  "turns": 2,
  "stop_reason": "end_turn",
  "is_error": false
}
```

Pass `session_id` from a previous response back in the next request to continue the same conversation.

### `GET /health`

Returns `{"status": "ok"}` — no authentication required.

## Example

```bash
export API_KEY=your-secret-token

curl -s -X POST http://localhost:8080/v1/commands \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 2 + 2?", "max_turns": 1}' | jq .
```

## Tests

```bash
pytest tests/ -v
```
