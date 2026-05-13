from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db.session import get_db_session
from app.crud import ticket as ticket_crud
from app.api.schemas.ticket import (
    TicketCreate,
    TicketUpdate,
    TicketResponse,
    TicketListResponse,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket_endpoint(
    ticket_in: TicketCreate, db: AsyncSession = Depends(get_db_session)
) -> TicketResponse:
    """
    Создаёт новую заявку.

    - **thread_id**: идентификатор сессии пользователя
    - **user_input**: текст заявки (1-10000 символов)
    - **priority**: low, medium, high или critical (по умолчанию medium)
    """
    db_ticket = await ticket_crud.create_ticket(db, ticket_in)

    # Конвертируем ORM-объект в Pydantic-схему для ответа
    return TicketResponse.model_validate(db_ticket)


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket_endpoint(
    ticket_id: int, db: AsyncSession = Depends(get_db_session)
) -> TicketResponse:
    """Получает заявку по id."""
    db_ticket = await ticket_crud.get_ticket_by_id(db, ticket_id)

    if not db_ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Заявка с id={ticket_id} не найдена",
        )

    return TicketResponse.model_validate(db_ticket)


@router.get("/", response_model=TicketListResponse)
async def list_tickets_endpoint(
    thread_id: str = Query(
        ..., min_length=1, description="Идентификатор сессии для фильтрации"
    ),
    skip: int = Query(0, ge=0, description="Пропустить первые N записей"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальное число записей"),
    db: AsyncSession = Depends(get_db_session),
) -> TicketListResponse:
    """
    Получает список заявок для сессии с пагинацией.

    - **thread_id**: обязательный параметр для фильтрации
    - **skip**: смещение для пагинации (по умолчанию 0)
    - **limit**: число записей на странице (1-1000, по умолчанию 100)
    """
    tickets, total = await ticket_crud.get_tickets_by_thread(db, thread_id, skip, limit)

    return TicketListResponse(
        items=[TicketResponse.model_validate(t) for t in tickets],
        total=total,
        page=skip // limit + 1,
        page_size=limit,
    )


@router.patch("/{ticket_id}", response_model=TicketResponse)
async def update_ticket_endpoint(
    ticket_id: int,
    ticket_update: TicketUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> TicketResponse:
    """Частично обновляет заявку по id."""
    db_ticket = await ticket_crud.update_ticket(db, ticket_id, ticket_update)

    if not db_ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Заявка с id={ticket_id} не найдена",
        )

    return TicketResponse.model_validate(db_ticket)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket_endpoint(
    ticket_id: int, db: AsyncSession = Depends(get_db_session)
) -> None:
    """Удаляет заявку по id. Возвращает 204 без тела ответа."""
    success = await ticket_crud.delete_ticket(db, ticket_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Заявка с id={ticket_id} не найдена",
        )

    return None
