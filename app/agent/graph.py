from typing import Literal

from app.agent.nodes.alert import send_critical_alert
from app.agent.nodes.chat_handler import chat_handler
from app.agent.nodes.classifier import classify_ticket
from app.agent.nodes.confirmation import confirmation_node
from app.agent.nodes.dialog_end import dialog_end
from app.agent.nodes.prioritizer import prioritize_ticket
from app.agent.nodes.saver import save_ticket
from app.agent.nodes.tagger import tag_ticket
from app.agent.state import AgentState
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph


def route_after_chat(state: AgentState) -> str:
    """После chat_handler: follow-up (в т.ч. close+resolve), end без ticket, или classifier.

    Важно: ticket_id проверяется раньше dialog_closed, чтобы success-close
    на follow-up дошёл до async dialog_end и обновил статус заявки.
    """
    if state.ticket_id is not None:
        return "dialog_end"
    if state.dialog_closed:
        return "end"
    return "classifier"


def route_after_tagger(state: AgentState) -> Literal["alert", "saver"]:
    """Маршрутизация после теггера: critical → alert, high+confirmation → alert, иначе → saver."""

    if state.needs_alert():
        return "alert"
    elif state.needs_confirmation():
        # Для high + requires_approval: сначала алерт, потом подтверждение
        return "alert"
    return "saver"


def route_after_alert(state: AgentState) -> Literal["saver"]:
    """После алерта: если нужно подтверждение → confirmation, иначе → saver."""

    if state.needs_confirmation():
        return "confirmation"
    return "saver"


def route_after_confirmation(state: AgentState) -> str:
    """После подтверждения: если отклонено → END, иначе → saver."""
    if state.confirmed is False:
        return "end"  # не сохраняем отклонённые заявки
    return "saver"


def build_agent_graph(checkpointer: BaseCheckpointSaver | None = None):
    """
    Строит и компилирует граф агента с опциональной поддержкой чекпоинтов.

    Args:
        checkpointer: Экземпляр хранилища чекпоинтов (опционально)

    Returns:
        Скомпилированный граф (CompiledStateGraph)
    """

    workflow = StateGraph(AgentState)

    # Добавление узлов
    workflow.add_node("chat", chat_handler)
    workflow.add_node("classifier", classify_ticket)
    workflow.add_node("prioritizer", prioritize_ticket)
    workflow.add_node("tagger", tag_ticket)
    workflow.add_node("alert", send_critical_alert)
    workflow.add_node("saver", save_ticket)
    workflow.add_node("confirmation", confirmation_node)
    workflow.add_node("dialog_end", dialog_end)
    workflow.add_node(
        "end", lambda s: {"dialog_closed": True}
    )  # ← Узел-заглушка для отклонённых

    # Линейные переходы
    workflow.add_edge(START, "chat")
    workflow.add_edge("classifier", "prioritizer")
    workflow.add_edge("prioritizer", "tagger")
    workflow.add_edge("dialog_end", END)
    workflow.add_conditional_edges(
        "chat",
        route_after_chat,
        ["classifier", "end", "dialog_end"],
    )
    workflow.add_conditional_edges(
        "tagger",
        route_after_tagger,
        ["alert", "saver"],
    )
    workflow.add_conditional_edges(
        "alert",
        route_after_alert,
        ["saver", "confirmation"],
    )
    workflow.add_conditional_edges(
        "confirmation",
        route_after_confirmation,
        ["saver", "end"],
    )

    # Завершение
    workflow.add_edge("saver", END)
    workflow.add_edge("end", END)

    return workflow.compile(checkpointer=checkpointer)
