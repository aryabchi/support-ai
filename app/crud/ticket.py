from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete

from app.api.schemas.ticket import TicketCreate, TicketUpdate
from app.db.models import Ticket, TicketHistory, TicketPriority, TicketStatus


async def create_ticket(session: AsyncSession, ticket_in: TicketCreate) -> Ticket:
    """
    Создаёт новую заявку в БД.

    Args:
        session: Асинхронная сессия SQLAlchemy
        ticket_in: Валидированные данные из схемы TicketCreate

    Returns:
        Созданный объект Ticket с присвоенным id
    """
    # Преобразуем строковые значения в enum, если переданы
    priority_enum = (
        TicketPriority(ticket_in.priority)
        if ticket_in.priority
        else TicketPriority.MEDIUM
    )

    db_ticket = Ticket(
        thread_id=ticket_in.thread_id,
        user_input=ticket_in.user_input,
        category=ticket_in.category,
        priority=priority_enum,
        tags=ticket_in.tags,
        status=TicketStatus.NEW,
    )

    session.add(db_ticket)
    await session.flush()  # Получаем id без коммита
    await session.refresh(
        db_ticket
    )  # Загружаем значения по умолчанию (created_at и т.д.)

    return db_ticket


async def get_ticket_by_id(session: AsyncSession, ticket_id: int) -> Ticket | None:
    """
    Получает заявку по id.

    Returns:
        Объект Ticket или None, если не найдено
    """
    result = await session.scalar(
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .options(selectinload(Ticket.history))
    )
    return result


async def get_tickets_by_thread(
    session: AsyncSession, thread_id: str, skip: int = 0, limit: int = 100
) -> tuple[list[Ticket], int]:
    """
    Получает список заявок для сессии с пагинацией.

    Returns:
        Кортеж (список заявок, общее число заявок для сессии)
    """
    # Запрос для получения общего числа (для пагинации)
    count_stmt = (
        select(func.count()).select_from(Ticket).where(Ticket.thread_id == thread_id)
    )
    total = await session.scalar(count_stmt)

    # Запрос для получения данных с пагинацией
    stmt = (
        select(Ticket)
        .where(Ticket.thread_id == thread_id)
        .order_by(Ticket.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    result = await session.scalars(stmt)
    tickets = result.all()

    return tickets, total


async def update_ticket(
    session: AsyncSession, ticket_id: int, ticket_update: TicketUpdate
) -> Ticket | None:
    """
    Частично обновляет заявку.

    Обновляются только переданные поля (не-None значения).

    Returns:
        Обновлённый объект Ticket или None, если не найдено
    """
    # Собираем только переданные поля
    update_data = ticket_update.model_dump(exclude_unset=True, exclude_none=True)

    if not update_data:
        # Нечего обновлять — возвращаем текущее значение
        return await get_ticket_by_id(session, ticket_id)

    # Конвертируем строки в enum, если нужно
    if "priority" in update_data:
        update_data["priority"] = TicketPriority(update_data["priority"])
    if "status" in update_data:
        update_data["status"] = TicketStatus(update_data["status"])

    # Выполняем UPDATE запрос
    stmt = (
        update(Ticket)
        .where(Ticket.id == ticket_id)
        .values(**update_data)
        .returning(Ticket)
    )

    result = await session.scalar(stmt)
    await session.commit()

    # Если нужно — загружаем связанные данные
    if result:
        await session.refresh(result, attribute_names=["history"])

    return result


async def delete_ticket(session: AsyncSession, ticket_id: int) -> bool:
    """
    Удаляет заявку по id.

    Returns:
        True если удалено, False если не найдено
    """
    stmt = delete(Ticket).where(Ticket.id == ticket_id)
    result = await session.execute(stmt)

    await session.commit()

    return result.rowcount > 0


async def add_ticket_history(
    session: AsyncSession,
    ticket_id: int,
    event_type: str,
    old_value: str | None = None,
    new_value: str | None = None,
) -> TicketHistory:
    """
    Добавляет запись в историю изменений заявки.

    Returns:
        Созданный объект TicketHistory
    """
    history = TicketHistory(
        ticket_id=ticket_id,
        event_type=event_type,
        old_value=old_value,
        new_value=new_value,
    )

    session.add(history)
    await session.flush()

    return history
