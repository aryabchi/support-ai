import time

from app.agent.state import AgentState
from app.api.schemas.ticket import TicketCreate
from app.crud import ticket as ticket_crud
from app.db.models.ticket import TicketStatus
from app.logging_config import logger
from langgraph.config import RunnableConfig


async def save_ticket(state: AgentState, config: RunnableConfig) -> dict:
    """
    Сохраняет обработанную заявку в базу данных.
    Сессия БД извлекается из config["configurable"].
    """
    start_time = time.time()
    thread_id = state.thread_id
    logger.debug(f"[{thread_id}] Начало сохранения заявки")

    # Извлекаем сессию из конфигурации
    session = config["configurable"].get("session")

    if not session:
        logger.error(f"[{thread_id}] БД не подключена")
        return AgentState(
            thread_id=state.thread_id,
            user_input=state.user_input,
            category=state.category,
            priority=state.priority,
            tags=state.tags,
            error=f"{state.error or ''} save_failed: БД не подключена".strip(),
            reasoning=f"{state.reasoning or ''} | Ошибка сохранения".strip(" |"),
            done=True,
        ).to_dict()

    try:
        ticket_in = TicketCreate(
            thread_id=state.thread_id,
            user_input=state.user_input,
            category=state.category,
            priority=state.priority,
            tags=state.tags,
        )

        # Критичные и подтверждённые HIL-заявки сразу переводим в работу
        if state.priority == "critical" or (
            state.requires_approval and state.confirmed is True
        ):
            initial_status = TicketStatus.IN_PROGRESS
        else:
            initial_status = TicketStatus.NEW
        db_ticket = await ticket_crud.create_ticket(
            session, ticket_in, status=initial_status
        )

        await ticket_crud.add_ticket_history(
            session=session,
            ticket_id=db_ticket.id,
            event_type="agent_processed",
            new_value=state.reasoning,
        )
        elapsed = time.time() - start_time
        logger.info(
            f"[{thread_id}] Заявка id={db_ticket.id} сохранена в БД",
            extra={
                "thread_id": thread_id,
                "ticket_id": str(db_ticket.id),
                "elapsed_ms": round(elapsed * 1000, 2),
            },
        )
        return AgentState(
            thread_id=state.thread_id,
            user_input=state.user_input,
            category=state.category,
            priority=state.priority,
            tags=state.tags,
            reasoning=f"{state.reasoning or ''} | Сохранено в БД (id={db_ticket.id})".strip(
                " |"
            ),
            done=True,
            ticket_id=db_ticket.id,
        ).to_dict()

    except Exception as e:
        elapsed = time.time() - start_time
        logger.exception(
            f"[{thread_id}] Неожиданная ошибка сохранения заявки",
            extra={
                "thread_id": thread_id,
                "error": str(e),
                "elapsed_ms": round(elapsed * 1000, 2),
            },
        )
        return AgentState(
            thread_id=state.thread_id,
            user_input=state.user_input,
            category=state.category,
            priority=state.priority,
            tags=state.tags,
            error=f"{state.error or ''} save_failed: {str(e)}".strip(),
            reasoning=f"{state.reasoning or ''} | Ошибка сохранения".strip(" |"),
            done=True,
        ).to_dict()
