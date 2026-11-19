from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    groq_api_key: str = Field(default="")
    groq_model: str = "llama-3.3-70b-versatile"
    mcp_server_url: str = "http://localhost:8001/mcp"
    mcp_auth_token: str = ""
    request_timeout_seconds: float = 30.0
    log_level: str = "INFO"
    environment: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
