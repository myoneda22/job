from pydantic_settings import BaseSettings, SettingsConfigDict
from claude_code_sdk.types import PermissionMode


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    api_key: str = "changeme"
    port: int = 8080
    host: str = "0.0.0.0"
    max_turns: int = 10
    model: str = "claude-sonnet-4-6"
    permission_mode: PermissionMode = "bypassPermissions"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
