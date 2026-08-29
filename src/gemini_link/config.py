"""Settings loading: environment variables, with optional ``.env`` support.

API keys are only ever read from the environment or a git-ignored ``.env``.
Nothing in this package accepts a key as a committed literal, and
:func:`redact` is used everywhere a key could otherwise reach a log line.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigError

# Sensible default: newest GA flash model as of the last live check against
# ListModels.  Override with GEMINI_MODEL; `cli.py models` prints the live list.
DEFAULT_GEMINI_MODEL = "gemini-3.7-flash"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"


def load_dotenv(path: str | os.PathLike[str] | None = None, *, override: bool = False) -> dict[str, str]:
    """Load ``KEY=value`` pairs from a ``.env`` file into ``os.environ``.

    Deliberately dependency-free and deliberately small: it handles the subset
    of ``.env`` syntax this project uses (comments, blank lines, ``export``
    prefixes, single/double quoted values) and ignores anything else rather
    than guessing.  Real process environment wins unless ``override`` is set,
    so a key exported in the shell is never silently replaced by a stale file.
    """
    env_path = Path(path) if path is not None else _find_dotenv()
    loaded: dict[str, str] = {}
    if env_path is None or not env_path.is_file():
        return loaded

    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        loaded[key] = value
        if override or key not in os.environ:
            os.environ[key] = value
    return loaded


def _find_dotenv(start: Path | None = None) -> Path | None:
    """Walk up from ``start`` looking for a ``.env``, stopping at the repo root."""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
        if (directory / ".git").exists():
            break
    return None


def redact(secret: str | None) -> str:
    """Render a key safe to print: keeps just enough to identify which one it is."""
    if not secret:
        return "<unset>"
    if len(secret) <= 8:
        return "***"
    return f"{secret[:4]}...{secret[-4:]}"


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None
    gemini_model: str
    anthropic_api_key: str | None
    anthropic_model: str
    timeout: float
    max_retries: int

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    def require_gemini_key(self) -> str:
        if not self.gemini_api_key:
            raise ConfigError(
                "GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in, "
                "or export GEMINI_API_KEY. Issue a key at https://aistudio.google.com/apikey"
            )
        return self.gemini_api_key

    def require_anthropic_key(self) -> str:
        if not self.anthropic_api_key:
            raise ConfigError(
                "ANTHROPIC_API_KEY is not set. It is only needed for the Claude<->Gemini "
                "comparison; set it in .env or export it."
            )
        return self.anthropic_api_key

    def describe(self) -> str:
        """One-line summary safe to print — keys are redacted."""
        return (
            f"gemini={self.gemini_model} key={redact(self.gemini_api_key)} | "
            f"anthropic={self.anthropic_model} key={redact(self.anthropic_api_key)} | "
            f"timeout={self.timeout}s retries={self.max_retries}"
        )


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def load_settings(*, dotenv: bool = True) -> Settings:
    if dotenv:
        load_dotenv()
    return Settings(
        gemini_api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or None,
        gemini_model=os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL,
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        anthropic_model=os.environ.get("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL,
        timeout=_float_env("GEMINI_TIMEOUT", 180.0),
        max_retries=_int_env("GEMINI_MAX_RETRIES", 4),
    )
