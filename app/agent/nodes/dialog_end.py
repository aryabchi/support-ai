"""Follow-up finalize: resolve ticket on success close."""

import time

from app.agent.state import AgentState
from app.api.schemas.ticket import TicketUpdate
from app.crud import ticket as ticket_crud
from app.logging_config import logger
from langgraph.config import RunnableConfig


async def dialog_end(state: AgentState, config: RunnableConfig) -> dict:
    """
    Завершение follow-up ветки после chat_handler.

    При close_reason=success обновляет статус заявки на resolved.
    Ответ пользователю уже сформирован в chat_handler.
    """
    thread_id = state.thread_id
    start_time = time.time()

    if state.close_reason != "success":
        logger.debug(
            f"[{thread_id}] dialog_end без resolve "
            f"(close_reason={state.close_reason!r})"
        )
        return {}

    if not state.ticket_id:
        logger.warning(
            f"[{thread_id}] success close без ticket_id — статус не обновлён"
        )
        return {}

    session = config["configurable"].get("session")
    if not session:
        logger.error(
            f"[{thread_id}] success close: БД не подключена, "
            f"ticket_id={state.ticket_id} не переведён в resolved"
        )
        return {
            "error": f"{state.error or ''} resolve_failed: БД не подключена".strip(),
        }

    try:
        updated = await ticket_crud.update_ticket(
            session,
            state.ticket_id,
            TicketUpdate(status="resolved"),
        )
        if updated is None:
            logger.warning(
                f"[{thread_id}] success close: заявка id={state.ticket_id} не найдена"
            )
            return {
                "error": (
                    f"{state.error or ''} resolve_failed: ticket not found"
                ).strip(),
            }

        await ticket_crud.add_ticket_history(
            session=session,
            ticket_id=state.ticket_id,
            event_type="resolved_by_user",
            new_value="resolved",
        )

        elapsed = time.time() - start_time
        logger.info(
            f"[{thread_id}] Заявка id={state.ticket_id} переведена в resolved",
            extra={
                "thread_id": thread_id,
                "ticket_id": str(state.ticket_id),
                "close_reason": state.close_reason,
                "elapsed_ms": round(elapsed * 1000, 2),
            },
        )
        return {}

    except Exception as exc:
        elapsed = time.time() - start_time
        logger.exception(
            f"[{thread_id}] Ошибка resolve при success close",
            extra={
                "thread_id": thread_id,
                "ticket_id": str(state.ticket_id),
                "error": str(exc),
                "elapsed_ms": round(elapsed * 1000, 2),
            },
        )
        return {
            "error": f"{state.error or ''} resolve_failed: {exc}".strip(),
        }
