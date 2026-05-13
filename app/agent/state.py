from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class AgentState(BaseModel):
    """Состояние агента обработки заявки."""

    model_config = ConfigDict(extra="allow")

    # === Входные данные ===
    thread_id: str = Field(..., min_length=1)
    user_input: str = Field(..., min_length=1)

    # === Результаты обработки ===
    category: Literal["technical", "billing", "feature", "other"] | None = None
    priority: Literal["low", "medium", "high", "critical"] | None = None
    tags: list[str] | None = None
    reasoning: str | None = None

    # === Управление потоком ===
    done: bool = False
    alert_sent: bool = False

    # === Обработка ошибок ===
    error: str | None = None

    # === Дополнительные поля ===
    ticket_id: int | None = None

    def to_dict(self) -> dict:
        """Конвертирует состояние в dict для обновления в LangGraph."""
        return self.model_dump(exclude_unset=True)

    def needs_alert(self) -> bool:
        """Проверяет, нужно ли отправить Telegram-алерт."""
        return self.priority == "critical" and not self.alert_sent
