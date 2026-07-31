import time

import httpx
from app.agent.state import AgentState
from app.config import get_settings
from app.logging_config import logger
from langgraph.config import RunnableConfig


async def send_critical_alert(state: AgentState, config: RunnableConfig) -> dict:
    """
    Отправляет Telegram-алерт для критичных заявок.

    Зависимости извлекаются из config["configurable"].
    """
    start_time = time.time()
    thread_id = state.thread_id
    logger.debug(f"[{thread_id}] Начало алертинга")

    settings = get_settings()

    # Извлекаем Telegram-клиент из конфигурации
    telegram_client = config["configurable"].get("telegram_client")

    if not telegram_client or not settings.TELEGRAM_CHAT_ID:
        logger.error(f"[{thread_id}] Telegram не настроен. Алерт не отправлен")
        return AgentState(
            thread_id=state.thread_id,
            user_input=state.user_input,
            category=state.category,
            priority=state.priority,
            tags=state.tags,
            alert_sent=False,
            error=f"{state.error or ''} alert_failed: Telegram не настроен".strip(),
            reasoning=f"{state.reasoning or ''} | Алерт не отправлен".strip(" |"),
        ).to_dict()

    message = f"""*Заявка требует внимания*

*Категория:* {state.category or "не определена"}
*Приоритет:* {state.priority.upper()}
*Текст:* {state.user_input[:200]}{'...' if len(state.user_input) > 200 else ''}
*Теги:* {', '.join(state.tags) if state.tags else 'нет'}
*Сессия:* `{state.thread_id}`

{state.reasoning or ''}
"""

    try:
        response = await telegram_client.post(
            "/sendMessage",
            json={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
            },
        )
        response.raise_for_status()

        return AgentState(
            thread_id=state.thread_id,
            user_input=state.user_input,
            category=state.category,
            priority=state.priority,
            tags=state.tags,
            alert_sent=True,
            reasoning=f"{state.reasoning or ''} | Алерт отправлен в Telegram".strip(
                " |"
            ),
        ).to_dict()

    except httpx.HTTPError as e:
        return AgentState(
            thread_id=state.thread_id,
            user_input=state.user_input,
            category=state.category,
            priority=state.priority,
            tags=state.tags,
            alert_sent=False,
            error=f"{state.error or ''} alert_failed: {str(e)}".strip(),
            reasoning=f"{state.reasoning or ''} | Ошибка отправки алерта".strip(" |"),
        ).to_dict()
