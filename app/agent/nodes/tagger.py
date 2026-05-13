import json
from app.agent.llm import llm
from app.agent.state import AgentState


def tag_ticket(state: AgentState) -> dict:
    """Назначает теги заявке."""

    prompt = f"""Ты назначаешь теги заявке в службу поддержки.
Выбери 0-3 наиболее релевантных тега из списка:

login, password, access, payment, billing, subscription, 
refund, bug, error, crash, feature, improvement, ui, ux, 
api, integration, mobile, web, documentation

Категория: {state.category or "other"}
Приоритет: {state.priority or "medium"}
Текст: {state.user_input}

Отвечай ТОЛЬКО валидным JSON-массивом строк: ["login", "bug"] или []

Теги:"""

    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        tags = json.loads(content)

        # Валидация: список строк, максимум 3 элемента
        if not isinstance(tags, list) or len(tags) > 3:
            tags = []
        elif not all(isinstance(t, str) for t in tags):
            tags = []

        return AgentState(
            thread_id=state.thread_id,
            user_input=state.user_input,
            category=state.category,
            priority=state.priority,
            tags=tags if tags else None,
            reasoning=f"{state.reasoning or ''} | Теги: {tags}".strip(" |"),
        ).to_dict()

    except Exception as e:
        return AgentState(
            thread_id=state.thread_id,
            user_input=state.user_input,
            category=state.category,
            priority=state.priority,
            tags=None,
            error=f"{state.error or ''} tagging_failed: {str(e)}".strip(),
            reasoning=f"{state.reasoning or ''} | Ошибка тегирования".strip(" |"),
        ).to_dict()
