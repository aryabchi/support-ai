import httpx
from functools import lru_cache
from contextlib import asynccontextmanager

from app.config import get_settings
from app.agent.graph import build_agent_graph


@lru_cache
def get_telegram_client():
    """
    Создаёт и кэширует HTTP-клиент для Telegram Bot API.
    """
    settings = get_settings()

    if not settings.TELEGRAM_BOT_TOKEN:
        return None

    base_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"

    return httpx.AsyncClient(
        base_url=base_url, timeout=httpx.Timeout(10.0, connect=5.0)
    )


@asynccontextmanager
async def get_telegram_client_context():
    """
    Context manager для Telegram-клиента.
    Гарантирует закрытие клиента после использования.
    """
    client = get_telegram_client()
    if client:
        try:
            yield client
        finally:
            await client.aclose()
    else:
        yield None


@lru_cache
def get_agent_graph():
    """
    Создаёт и кэширует компилированный граф агента.
    """
    return build_agent_graph()
