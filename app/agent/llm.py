import os
from functools import lru_cache
from langchain_ollama import ChatOllama

from app.config import get_settings


@lru_cache(maxsize=1)
def get_llm() -> ChatOllama:
    """
    Возвращает кэшированный экземпляр ChatOllama.
    """
    settings = get_settings()
    # Настройка LangSmith через переменные окружения
    if settings.LANGSMITH_TRACING:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY or ""
        os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
        if settings.LANGSMITH_ENDPOINT:
            os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT

    return ChatOllama(
        base_url=str(settings.OLLAMA_BASE_URL),
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        num_predict=settings.LLM_MAX_TOKENS,
    )


llm = get_llm()
