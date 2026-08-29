"""Gemini integration for the job-hunting (就活) workflow.

Four entry points, all sharing one client:

* :mod:`gemini_link.gemini`     — a dependency-free Gemini API client
* :mod:`gemini_link.shukatsu`   — grounded company research for Airtable
* :mod:`gemini_link.compare`    — Claude vs Gemini cross-checking
* :mod:`gemini_link.mcp_server` — an MCP server exposing all of it to Claude Code
"""

from .config import Settings, load_dotenv, load_settings, redact
from .errors import (
    ApiError,
    ConfigError,
    EmptyResponseError,
    GeminiLinkError,
    RateLimitError,
    RetrievalError,
)
from .gemini import FunctionCall, GeminiClient, GeminiResponse, RetrievedUrl, Source

__version__ = "0.1.0"

__all__ = [
    "ApiError",
    "ConfigError",
    "EmptyResponseError",
    "FunctionCall",
    "GeminiClient",
    "GeminiLinkError",
    "GeminiResponse",
    "RateLimitError",
    "RetrievalError",
    "RetrievedUrl",
    "Settings",
    "Source",
    "load_dotenv",
    "load_settings",
    "redact",
    "__version__",
]
