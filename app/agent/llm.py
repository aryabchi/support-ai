from functools import lru_cache
from langchain_ollama import ChatOllama

from app.config import get_settings


@lru_cache(maxsize=1)
def get_llm() -> ChatOllama:
    """
    Возвращает кэшированный экземпляр ChatOllama.
    """
    settings = get_settings()

    return ChatOllama(
        base_url=str(settings.OLLAMA_BASE_URL),
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        num_predict=settings.LLM_MAX_TOKENS,
    )


llm = get_llm()
