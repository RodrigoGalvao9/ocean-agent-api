from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    groq_api_key: str = Field(default="")
    groq_model: str = "openai/gpt-oss-120b"
    mcp_server_url: str = "http://localhost:8001/mcp"
    mcp_auth_token: str = ""
    # Ferramentas do MCP que o chat público pode usar (separadas por vírgula).
    # set_speed / get_fleet_state ficam de fora de propósito.
    allowed_tools: str = "buscar_conhecimento,listar_topicos"
    request_timeout_seconds: float = 30.0
    log_level: str = "INFO"
    environment: str = "development"


    @property
    def allowed_tool_names(self) -> set[str]:
        return {n.strip() for n in self.allowed_tools.split(",") if n.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
