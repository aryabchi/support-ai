import time
from datetime import datetime, timezone

from app.agent.checkpointer import get_checkpointer
from app.agent.state import AgentState
from app.api.schemas.ticket import (
    ConfirmRequest,
    ConfirmResponse,
    TicketCreate,
    TicketListResponse,
    TicketResponse,
    TicketUpdate,
)
from app.config import Settings, get_settings
from app.core.dependencies import get_agent_graph, get_telegram_client_context
from app.crud import ticket as ticket_crud
from app.db.session import get_db_session
from app.logging_config import logger
from fastapi import APIRouter, Depends, HTTPException, Query, status
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket_endpoint(
    ticket_in: TicketCreate,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> TicketResponse:
    """Создаёт заявку с обработкой через агента."""

    start_time = time.time()
    thread_id = ticket_in.thread_id
    logger.info(f"[{thread_id}] Получен запрос на создание заявки")

    db_url = str(settings.DATABASE_URL)

    graph_builder = get_agent_graph()

    initial_state = AgentState(
        thread_id=ticket_in.thread_id,
        user_input=ticket_in.user_input,
    )

    # Запуск агента с передачей зависимостей через config
    async with get_checkpointer(
        db_url
    ) as checkpointer, get_telegram_client_context() as telegram_client:
        # Компилируем граф с checkpointer для этого запроса
        agent_graph = graph_builder(checkpointer=checkpointer)
        result_state = await agent_graph.ainvoke(
            initial_state,
            config={
                "configurable": {
                    "session": db,
                    "telegram_client": telegram_client,
                    "thread_id": ticket_in.thread_id,
                }
            },
        )

    if "__interrupt__" in result_state:
        # Заявка ждёт подтверждения — возвращаем специальный статус
        elapsed = time.time() - start_time
        logger.info(f"[{thread_id}] Заявка ожидает подтверждения пользователя")
        return TicketResponse(
            id=0,
            thread_id=thread_id,
            user_input=ticket_in.user_input,
            category=result_state.get("category"),
            priority=result_state.get("priority"),
            tags=result_state.get("tags"),
            status="awaiting_confirmation",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    if (
        result_state.get("error")
        and ("alert_failed" not in result_state["error"])
        and not result_state.get("ticket_id")
    ):
        # Ok if error is connected with alerting ("alert_failed")
        elapsed = time.time() - start_time
        logger.error(
            f"[{thread_id}] Ошибка агента: {result_state['error']}",
            extra={
                "thread_id": thread_id,
                "error": result_state["error"],
                "elapsed_ms": round(elapsed * 1000, 2),
            },
        )
        raise HTTPException(status_code=500, detail=result_state["error"])

    # Получаем уже сохранённую заявку по id от агента
    if not result_state.get("ticket_id"):
        elapsed = time.time() - start_time
        logger.error(
            f"[{thread_id}] Агент не вернул ticket_id",
            extra={
                "thread_id": thread_id,
                "elapsed_ms": round(elapsed * 1000, 2),
            },
        )
        raise HTTPException(status_code=500, detail="Agent did not return ticket_id")

    # Получаем сохранённую заявку
    db_ticket = await ticket_crud.get_ticket_by_id(db, result_state["ticket_id"])
    elapsed = time.time() - start_time
    logger.info(
        f"[{thread_id}] Заявка создана: id={db_ticket.id}",
        extra={
            "thread_id": thread_id,
            "ticket_id": db_ticket.id,
            "category": db_ticket.category,
            "priority": db_ticket.priority,
            "tags_count": len(db_ticket.tags) if db_ticket.tags else 0,
            "elapsed_ms": round(elapsed * 1000, 2),
        },
    )
    return TicketResponse.model_validate(db_ticket)


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket_endpoint(
    ticket_id: int, db: AsyncSession = Depends(get_db_session)
) -> TicketResponse:
    """Получает заявку по id."""
    start_time = time.time()
    logger.debug(f"Получен запрос на получение заявки: id={ticket_id}")

    db_ticket = await ticket_crud.get_ticket_by_id(db, ticket_id)

    if not db_ticket:
        elapsed = time.time() - start_time
        logger.warning(
            f"Заявка не найдена: id={ticket_id}",
            extra={
                "ticket_id": ticket_id,
                "elapsed_ms": round(elapsed * 1000, 2),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Заявка с id={ticket_id} не найдена",
        )
    elapsed = time.time() - start_time
    logger.debug(
        f"Заявка получена: id={ticket_id}",
        extra={
            "ticket_id": ticket_id,
            "elapsed_ms": round(elapsed * 1000, 2),
        },
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
    start_time = time.time()
    logger.debug(
        f"Получен запрос на список заявок: thread_id={thread_id}, skip={skip}, limit={limit}"
    )

    tickets, total = await ticket_crud.get_tickets_by_thread(db, thread_id, skip, limit)
    elapsed = time.time() - start_time
    logger.debug(
        f"Список заявок получен: {len(tickets)} из {total}",
        extra={
            "thread_id": thread_id,
            "returned": len(tickets),
            "total": total,
            "skip": skip,
            "limit": limit,
            "elapsed_ms": round(elapsed * 1000, 2),
        },
    )
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
    start_time = time.time()
    logger.debug(f"Получен запрос на обновление заявки: id={ticket_id}")

    db_ticket = await ticket_crud.update_ticket(db, ticket_id, ticket_update)

    if not db_ticket:
        elapsed = time.time() - start_time
        logger.warning(
            f"Заявка не найдена для обновления: id={ticket_id}",
            extra={
                "ticket_id": ticket_id,
                "elapsed_ms": round(elapsed * 1000, 2),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Заявка с id={ticket_id} не найдена",
        )

    elapsed = time.time() - start_time
    logger.info(
        f"Заявка обновлена: id={ticket_id}",
        extra={
            "ticket_id": ticket_id,
            "updated_fields": ticket_update.model_dump(exclude_unset=True).keys(),
            "elapsed_ms": round(elapsed * 1000, 2),
        },
    )
    return TicketResponse.model_validate(db_ticket)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket_endpoint(
    ticket_id: int, db: AsyncSession = Depends(get_db_session)
) -> None:
    """Удаляет заявку по id. Возвращает 204 без тела ответа."""
    start_time = time.time()
    logger.debug(f"Получен запрос на удаление заявки: id={ticket_id}")

    success = await ticket_crud.delete_ticket(db, ticket_id)

    if not success:
        elapsed = time.time() - start_time
        logger.warning(
            f"Заявка не найдена для удаления: id={ticket_id}",
            extra={
                "ticket_id": ticket_id,
                "elapsed_ms": round(elapsed * 1000, 2),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Заявка с id={ticket_id} не найдена",
        )

    elapsed = time.time() - start_time
    logger.info(
        f"Заявка удалена: id={ticket_id}",
        extra={
            "ticket_id": ticket_id,
            "elapsed_ms": round(elapsed * 1000, 2),
        },
    )

    return None


@router.post(
    "/confirm",
    response_model=ConfirmResponse,
    description="Возобновление графа HIL /*Command(resume=decision)*/",
)
async def confirm_ticket_by_thread(
    request: ConfirmRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ConfirmResponse:
    """Возобновляет обработку заявки с решением пользователя по thread_id."""
    settings = get_settings()
    db_url = str(settings.DATABASE_URL)
    thread_id = request.thread_id

    logger.info(f"[{thread_id}] Получен запрос на подтверждение заявки")

    async with get_checkpointer(db_url) as checkpointer:
        graph = get_agent_graph()(checkpointer=checkpointer)
        snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id}})

        if not snapshot.interrupts:
            if not snapshot.values:
                raise HTTPException(status_code=404, detail="Сессия не найдена")
            raise HTTPException(
                status_code=400,
                detail="Нет ожидающего подтверждения для этой сессии",
            )

        async with get_telegram_client_context() as telegram_client:
            result = await graph.ainvoke(
                Command(resume=request.decision),
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "session": db,
                        "telegram_client": telegram_client,
                    }
                },
            )

    confirmed = result.get("confirmed", False)
    ticket_id = result.get("ticket_id") or 0

    if confirmed and ticket_id:
        db_ticket = await ticket_crud.get_ticket_by_id(db, ticket_id)
        ticket_status = db_ticket.status.value
    else:
        ticket_status = "rejected"

    return ConfirmResponse(
        ticket_id=ticket_id,
        confirmed=confirmed,
        status=ticket_status,
        message=result.get("confirmation_message"),
    )
