from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq

from src.core.config import Settings
from src.core.exceptions import ConfigurationError


def create_llm(settings: Settings) -> BaseChatModel:
    if not settings.groq_api_key:
        raise ConfigurationError("GROQ_API_KEY is required to execute chat requests")
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0,
        timeout=settings.request_timeout_seconds,
    )
