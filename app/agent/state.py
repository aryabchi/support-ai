from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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

    # === Поля для HIL (defaults for backward compat) ===
    requires_approval: bool = False  # Требуется ли подтверждение
    confirmed: bool | None = None  # Результат подтверждения
    confirmation_message: str | None = None  # Сообщение прерывания

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

    def needs_confirmation(self) -> bool:
        """Проверяет, нужно ли запросить подтверждение пользователя."""
        return (
            self.priority == "high"
            and self.requires_approval
            and self.confirmed is None
        )
