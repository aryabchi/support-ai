from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func

from app.db.base import Base


class TicketHistory(Base):
    """
    Модель истории изменений заявки.

    Таблица: ticket_history
    Используется для аудита и отладки работы агента.
    """

    __tablename__ = "ticket_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Связь с заявкой
    ticket_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Тип события: что изменилось
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)

    # Данные события: что было до и после
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Связь обратно с заявкой
    ticket: Mapped["Ticket"] = relationship(  # noqa: F821
        "Ticket", back_populates="history"
    )

    def __repr__(self) -> str:
        return f"TicketHistory id={self.id}"
