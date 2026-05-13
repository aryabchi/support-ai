from app.agent.llm import llm
from app.agent.state import AgentState


def prioritize_ticket(state: AgentState) -> dict:
    """Определяет приоритет заявки."""

    prompt = f"""Ты определяешь приоритет заявки в службу поддержки.
Оцени срочность обращения по шкале: critical, high, medium, low.

Критерии:
- critical: блокирующая проблема, угроза безопасности, массовый сбой
- high: важная функция не работает, влияет на бизнес-процессы
- medium: стандартный вопрос, не срочное улучшение
- low: косметическая правка, вопрос без срочности

Категория заявки: {state.category or "не определена"}
Текст обращения: {state.user_input}

Отвечай ТОЛЬКО одним словом: critical, high, medium или low.
Не используй знаки препинания.
Приоритет:"""

    try:
        response = llm.invoke(prompt)
        priority = response.content.strip().lower()

        valid_priorities = {"critical", "high", "medium", "low"}
        if priority not in valid_priorities:
            priority = "medium"

        return AgentState(
            thread_id=state.thread_id,
            user_input=state.user_input,
            category=state.category,
            priority=priority,
            reasoning=f"{state.reasoning or ''} | Приоритет: {priority}".strip(" |"),
        ).to_dict()

    except Exception as e:
        return AgentState(
            thread_id=state.thread_id,
            user_input=state.user_input,
            category=state.category,
            priority="medium",
            error=f"{state.error or ''} prioritization_failed: {str(e)}".strip(),
            reasoning=f"{state.reasoning or ''} | Ошибка приоритизации".strip(" |"),
        ).to_dict()
