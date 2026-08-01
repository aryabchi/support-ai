from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# === Схемы для создания заявки ===


class TicketCreate(BaseModel):
    """
    Схема для создания новой заявки.

    Используется для валидации входных данных в эндпоинте POST /tickets.
    """

    thread_id: str = Field(
        ..., min_length=1, max_length=64, description="Идентификатор сессии"
    )
    user_input: str = Field(
        ..., min_length=1, max_length=10000, description="Текст заявки"
    )
    category: str | None = Field(
        default=None, max_length=64, description="Категория заявки"
    )
    priority: str | None = Field(
        default="medium",
        pattern="^(low|medium|high|critical)$",
        description="Приоритет",
    )
    tags: list[str] | None = Field(default=None, description="Теги заявки")


# === Схемы для обновления заявки ===


class TicketUpdate(BaseModel):
    """
    Схема для частичного обновления заявки.

    Все поля опциональны — обновляются только переданные.
    """

    category: str | None = Field(default=None, max_length=64)
    priority: str | None = Field(default=None, pattern="^(low|medium|high|critical)$")
    tags: list[str] | None = Field(default=None)
    status: str | None = Field(
        default=None, pattern="^(new|in_progress|resolved|closed)$"
    )


# === Схемы для ответа ===


class TicketBase(BaseModel):
    """Базовая схема с общими полями заявки."""

    thread_id: str
    user_input: str
    category: str | None = None
    priority: str
    tags: list[str] | None = None
    status: str


class TicketResponse(TicketBase):
    """
    Полная схема ответа с метаданными.

    Используется для сериализации ответа в эндпоинтах GET.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    last_response: str | None = None
    messages_count: int | None = None


# === Схемы для истории диалога ===


class ChatMessage(BaseModel):
    """Сообщение пользователя в рамках диалога."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Текст сообщения (1-1000 символов)",
    )


class ChatResponse(BaseModel):
    """Ответ API для многошагового диалога."""

    thread_id: str
    messages: list[dict]
    last_response: str | None = None
    done: bool = False
    ticket_id: int | None = None
    category: str | None = None
    priority: str | None = None


class TicketListResponse(BaseModel):
    """Схема для списка заявок с пагинацией."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TicketResponse]
    total: int
    page: int
    page_size: int


# === Схемы для подтверждения заявки (HIL) ===


class ConfirmRequest(BaseModel):
    """Запрос на подтверждение/отклонение заявки по thread_id."""

    thread_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Идентификатор сессии (тот же, что при POST /tickets/)",
    )
    decision: str = Field(
        ...,
        pattern="^(yes|no)$",
        description="Решение пользователя: 'yes' для подтверждения, 'no' для отмены",
    )


class ConfirmResponse(BaseModel):
    """Ответ после подтверждения заявки."""

    model_config = ConfigDict(from_attributes=True)

    ticket_id: int
    confirmed: bool
    status: str
    message: str | None = None
