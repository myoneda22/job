from __future__ import annotations

import pytest

from gemini_link.config import Settings, load_dotenv, load_settings, redact
from gemini_link.errors import ConfigError


def test_load_dotenv_parses_comments_quotes_and_export(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "# a comment\n"
        "\n"
        "GEMINI_API_KEY=plain-value\n"
        'ANTHROPIC_API_KEY="quoted-value"\n'
        "export GEMINI_MODEL='gemini-3.7-flash'\n"
        "NOT_A_PAIR\n",
        encoding="utf-8",
    )
    loaded = load_dotenv(env)
    assert loaded == {
        "GEMINI_API_KEY": "plain-value",
        "ANTHROPIC_API_KEY": "quoted-value",
        "GEMINI_MODEL": "gemini-3.7-flash",
    }
    assert "NOT_A_PAIR" not in loaded


def test_real_environment_wins_over_dotenv(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", "from-shell")
    load_dotenv(env)
    assert load_settings(dotenv=False).gemini_api_key == "from-shell"


def test_dotenv_override_flag(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", "from-shell")
    load_dotenv(env, override=True)
    assert load_settings(dotenv=False).gemini_api_key == "from-file"


def test_missing_dotenv_is_not_an_error(tmp_path):
    assert load_dotenv(tmp_path / "nope.env") == {}


def test_google_api_key_is_accepted_as_a_fallback(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "alt-key")
    assert load_settings(dotenv=False).gemini_api_key == "alt-key"


def test_defaults_when_nothing_is_set():
    s = load_settings(dotenv=False)
    assert s.gemini_model == "gemini-3.7-flash"
    assert s.has_gemini is False
    assert s.has_anthropic is False


def test_require_keys_explains_how_to_fix(settings):
    with pytest.raises(ConfigError, match="GEMINI_API_KEY"):
        Settings(None, "m", None, "c", 1.0, 1).require_gemini_key()
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        settings.require_anthropic_key()


def test_bad_numeric_env_is_reported_by_name(monkeypatch):
    monkeypatch.setenv("GEMINI_TIMEOUT", "soon")
    with pytest.raises(ConfigError, match="GEMINI_TIMEOUT"):
        load_settings(dotenv=False)


@pytest.mark.parametrize(
    "secret,expected",
    [
        (None, "<unset>"),
        ("", "<unset>"),
        ("short", "***"),
        ("12345678", "***"),                       # boundary: <= 8 chars stays fully hidden
        ("XY.0000000000000wxyz", "XY.0...wxyz"),   # synthetic, shaped like a real key
    ],
)
def test_redact(secret, expected):
    assert redact(secret) == expected


def test_describe_never_prints_a_whole_key():
    s = Settings("super-secret-key-value", "m", "another-secret-value", "c", 1.0, 1)
    described = s.describe()
    assert "super-secret-key-value" not in described
    assert "another-secret-value" not in described
    assert "supe...alue" in described
