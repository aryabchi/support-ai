from langgraph.config import RunnableConfig
from app.agent.state import AgentState
from app.crud import ticket as ticket_crud
from app.api.schemas.ticket import TicketCreate


async def save_ticket(state: AgentState, config: RunnableConfig) -> dict:
    """
    Сохраняет обработанную заявку в базу данных.

    Сессия БД извлекается из config["configurable"].
    """
    # Извлекаем сессию из конфигурации
    session = config["configurable"].get("session")

    if not session:
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

        db_ticket = await ticket_crud.create_ticket(session, ticket_in)

        await ticket_crud.add_ticket_history(
            session=session,
            ticket_id=db_ticket.id,
            event_type="agent_processed",
            new_value=state.reasoning,
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
