from app.agent.state import AgentState
from app.logging_config import logger
from langgraph.types import interrupt


def confirmation_node(state: AgentState) -> dict:
    """
    Запрашивает подтверждение действия для заявок с высоким приоритетом.

    Вызывает interrupt() и ждёт решения пользователя.
    Возвращает статус подтверждения в состояние.
    """
    thread_id = state.thread_id
    logger.debug(f"[{thread_id}] Начало узла подтверждения")

    # Пропускаем, если подтверждение не требуется
    if not state.requires_approval:
        logger.debug(f"[{thread_id}] Подтверждение не требуется, пропускаем")
        return {"confirmed": True}

    # Формируем сообщение для пользователя
    ticket_id_display = state.ticket_id if state.ticket_id else "new"
    prompt = (
        f"Требуется подтверждение для заявки #{ticket_id_display}\n"
        f"Приоритет: {state.priority}\n"
        f"Категория: {state.category}\n"
        f"Сообщение: {state.user_input[:200]}{'...' if len(state.user_input) > 200 else ''}\n\n"
        f"Введите 'yes' для подтверждения или 'no' для отмены:"
    )

    logger.info(f"[{thread_id}] Запрос подтверждения отправлен пользователю")

    # Прерывание: ждём решения пользователя
    user_decision = interrupt(prompt)

    # Возвращаем результат в состояние
    if user_decision == "yes":
        logger.info(f"[{thread_id}] Заявка подтверждена пользователем")
        return {"confirmed": True, "confirmation_message": None}
    else:
        logger.info(f"[{thread_id}] Заявка отклонена пользователем")
        return {"confirmed": False, "confirmation_message": prompt}
