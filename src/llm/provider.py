from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

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


def create_openrouter_refiner(settings: Settings) -> BaseChatModel | None:
    if not settings.openrouter_api_key:
        return None
    return ChatOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        model=settings.openrouter_refiner_model,
        temperature=0,
        timeout=settings.request_timeout_seconds,
    )


def create_openrouter_validator(settings: Settings) -> BaseChatModel | None:
    if not settings.openrouter_api_key:
        return None
    return ChatOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        model=settings.openrouter_validator_model,
        temperature=0,
        timeout=settings.request_timeout_seconds,
    )
