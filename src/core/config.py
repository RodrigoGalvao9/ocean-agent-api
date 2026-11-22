from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    groq_api_key: str = Field(default="")
    groq_model: str = "openai/gpt-oss-120b"
    openrouter_api_key: str = Field(default="")
    openrouter_refiner_model: str = "nvidia/nemotron-3.5-lightning:free"
    openrouter_validator_model: str = "nvidia/nemotron-3-ultra:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_refiner_enabled: bool = True
    openrouter_refiner_timeout_seconds: float = 8.0
    openrouter_validator_timeout_seconds: float = 15.0
    mcp_server_url: str = "http://localhost:8001/mcp"
    mcp_auth_token: str = ""
    # Ferramentas do MCP que o chat público pode usar (separadas por vírgula). Todas são de
    # leitura. Nomes que o servidor ainda não expõe são ignorados na descoberta, então as
    # ferramentas planejadas já podem estar na lista. Os aliases antigos em português
    # (buscar_conhecimento, listar_topicos) ficam de fora de propósito: duplicariam as
    # ferramentas em inglês para o modelo.
    allowed_tools: str = (
        "search_maritime_knowledge,list_knowledge_topics,"
        "get_marine_conditions,get_tide_table,get_fishing_closures,"
        "search_vessels,find_fish_markets"
    )
    # Timeout das chamadas ao MCP quando ele está "acordado" (respondeu há pouco).
    request_timeout_seconds: float = 30.0
    # Partida a frio: no plano free do Render o MCP dorme após alguns minutos parado e
    # leva dezenas de segundos para acordar. Sem resposta recente, esperamos mais.
    mcp_cold_start_timeout_seconds: float = 60.0
    mcp_warm_window_seconds: float = 600.0
    # A lista de ferramentas muda raramente: guardamos por alguns minutos.
    mcp_tools_cache_ttl_seconds: float = 300.0
    # Limite do texto de cada ferramenta enviado ao modelo (controla custo em tokens).
    max_tool_output_chars: int = 12_000
    log_level: str = "INFO"
    environment: str = "development"

    # --- CORS ---------------------------------------------------------------
    # Origens do frontend, separadas por vírgula (ex.: https://ocean-frontend.onrender.com).
    cors_origins: str = "http://localhost:5173"

    # --- Proteção do chat público -------------------------------------------
    # Sessão assinada pelo backend para ownership das conversas.
    conversation_session_secret: str = ""
    # Sem REDIS_URL o limite roda em memória (vale para 1 instância e zera a cada deploy).
    redis_url: str = ""
    rate_limit_enabled: bool = True
    rate_limit_chat_per_minute: int = 8  # por IP
    rate_limit_chat_per_day: int = 100  # por IP
    rate_limit_global_per_minute: int = 60  # todos os clientes juntos (protege a cota do Groq)
    rate_limit_read_per_minute: int = 60  # listar/abrir/apagar conversas, por IP
    # Quantos proxies confiáveis ficam na frente da API (Render = 1). Define qual item
    # do X-Forwarded-For é o IP real; 0 ignora o header e usa o IP da conexão.
    trusted_proxy_hops: int = 1
    max_request_body_bytes: int = 16_384
    max_history_messages: int = 12  # mensagens anteriores enviadas ao LLM
    max_messages_per_conversation: int = 60
    max_conversations: int = 1000  # total em memória; a mais antiga sai primeiro

    # --- Observabilidade ----------------------------------------------------
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_sample_rate: float = 1.0
    # Captura de prompts e respostas é opt-in para evitar enviar conteúdo de usuário ao SaaS.
    langfuse_capture_content: bool = False
    # Protege o /metrics. Vazio = endpoint desligado fora do ambiente "development".
    metrics_token: str = ""

    @property
    def allowed_tool_names(self) -> set[str]:
        return set(_split(self.allowed_tools))

    @property
    def cors_origin_list(self) -> list[str]:
        return _split(self.cors_origins)

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
