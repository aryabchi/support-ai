"""
Unit-тесты async dialog_end (resolve на success close).
Запуск: pytest tests/test_dialog_end.py -v
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.agent.nodes.dialog_end import dialog_end
from app.agent.state import AgentState
from app.api.schemas.ticket import TicketUpdate


def _config(session=None):
    return {"configurable": {"session": session, "thread_id": "t1"}}


@pytest.mark.asyncio
async def test_success_close_updates_ticket_resolved():
    session = MagicMock()
    updated = MagicMock()
    with (
        patch(
            "app.agent.nodes.dialog_end.ticket_crud.update_ticket",
            new_callable=AsyncMock,
            return_value=updated,
        ) as mock_update,
        patch(
            "app.agent.nodes.dialog_end.ticket_crud.add_ticket_history",
            new_callable=AsyncMock,
        ) as mock_history,
    ):
        state = AgentState(
            thread_id="t1",
            user_input="Спасибо, помогло!",
            ticket_id=42,
            close_reason="success",
            dialog_closed=True,
        )
        result = await dialog_end(state, _config(session))

    assert result == {}
    mock_update.assert_awaited_once()
    args, kwargs = mock_update.await_args
    assert args[0] is session
    assert args[1] == 42
    assert isinstance(args[2], TicketUpdate)
    assert args[2].status == "resolved"
    mock_history.assert_awaited_once()
    assert mock_history.await_args.kwargs["event_type"] == "resolved_by_user"


@pytest.mark.asyncio
async def test_goodbye_does_not_update_ticket():
    with patch(
        "app.agent.nodes.dialog_end.ticket_crud.update_ticket",
        new_callable=AsyncMock,
    ) as mock_update:
        state = AgentState(
            thread_id="t1",
            user_input="пока",
            ticket_id=42,
            close_reason="goodbye",
            dialog_closed=True,
        )
        result = await dialog_end(state, _config(MagicMock()))

    assert result == {}
    mock_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_success_without_session_sets_error():
    state = AgentState(
        thread_id="t1",
        user_input="Спасибо, помогло!",
        ticket_id=7,
        close_reason="success",
        dialog_closed=True,
    )
    result = await dialog_end(state, _config(session=None))

    assert "resolve_failed" in (result.get("error") or "")


@pytest.mark.asyncio
async def test_followup_without_close_is_noop():
    with patch(
        "app.agent.nodes.dialog_end.ticket_crud.update_ticket",
        new_callable=AsyncMock,
    ) as mock_update:
        state = AgentState(
            thread_id="t1",
            user_input="ещё вопрос",
            ticket_id=42,
        )
        result = await dialog_end(state, _config(MagicMock()))

    assert result == {}
    mock_update.assert_not_awaited()
