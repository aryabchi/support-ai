import json
from tenacity import RetryError
from app.agent.llm import llm
from app.agent.state import AgentState
from app.agent.retry import with_llm_retry


@with_llm_retry(max_attempts=3)
def _tag_llm_call(prompt: str):
    """Внутренняя функция: только вызов LLM."""
    return llm.invoke(prompt)


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
        # 1. Вызов LLM с retry
        response = _tag_llm_call(prompt)
        content = response.content.strip()

        # 2. Парсинг JSON (может упасть с JSONDecodeError)
        tags = json.loads(content)

        # 3. Валидация структуры
        if not isinstance(tags, list):
            raise ValueError("Expected list of tags")

        # 5. Валидация типов элементов
        if not all(isinstance(t, str) for t in tags):
            raise ValueError("All tags must be strings")

        # 6. Валидация значений (фильтр по разрешённому набору)
        valid_tags = {
            "login",
            "password",
            "access",
            "payment",
            "billing",
            "bug",
            "error",
            "crash",
            "feature",
            "ui",
            "api",
        }
        tags = [t for t in tags if t in valid_tags]

        # 4. Валидация длины
        if len(tags) > 3:
            tags = tags[:3]

        return AgentState(
            thread_id=state.thread_id,
            user_input=state.user_input,
            category=state.category,
            priority=state.priority,
            tags=tags if tags else None,
            reasoning=f"{state.reasoning or ''} | Теги: {tags}".strip(" |"),
        ).to_dict()

    except RetryError:
        # Исчерпаны попытки вызова LLM
        return AgentState(
            thread_id=state.thread_id,
            user_input=state.user_input,
            category=state.category,
            priority=state.priority,
            tags=None,
            error="tagging_failed: retry_exhausted",
            reasoning=f"{state.reasoning or ''} | Ошибка тэгирования: исчерпаны повторные попытки".strip(
                " |"
            ),
        ).to_dict()

    except (json.JSONDecodeError, ValueError) as e:
        return AgentState(
            thread_id=state.thread_id,
            user_input=state.user_input,
            category=state.category,
            priority=state.priority,
            tags=None,
            error=f"tagging_failed: {type(e).__name__}".strip(),
            reasoning=f"{state.reasoning or ''} | Ошибка тэгирования: валидация ответа".strip(
                " |"
            ),
        ).to_dict()
