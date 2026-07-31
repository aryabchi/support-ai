import httpx
from functools import lru_cache
from contextlib import asynccontextmanager

from app.config import get_settings


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

    Создаёт новый httpx.AsyncClient на каждый запрос и закрывает его после использования.
    """
    settings = get_settings()

    if not settings.TELEGRAM_BOT_TOKEN:
        yield None
        return

    base_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(10.0, connect=5.0),
    ) as client:
        yield client


@lru_cache
def get_agent_graph():
    """
    Возвращает функцию для построения графа агента.

    Граф компилируется с checkpointer при вызове, поэтому кэшируем
    саму функцию build_agent_graph, а не результат её выполнения.
    """
    from app.agent.graph import build_agent_graph

    return build_agent_graph
