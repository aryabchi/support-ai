from typing import Literal

from app.agent.state import AgentState
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.agent.nodes.tagger import tag_ticket
from app.agent.nodes.saver import save_ticket
from app.agent.nodes.alert import send_critical_alert
from app.agent.nodes.classifier import classify_ticket
from app.agent.nodes.prioritizer import prioritize_ticket


def route_after_tagger(state: AgentState) -> Literal["alert", "saver"]:
    """Маршрутизация после теггера: critical → alert, иначе → saver."""
    if state.needs_alert():
        return "alert"
    return "saver"


def route_after_alert(state: AgentState) -> Literal["saver"]:
    """После алерта всегда идём в saver."""
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
    workflow.add_node("classifier", classify_ticket)
    workflow.add_node("prioritizer", prioritize_ticket)
    workflow.add_node("tagger", tag_ticket)
    workflow.add_node("alert", send_critical_alert)
    workflow.add_node("saver", save_ticket)

    # Линейные переходы
    workflow.add_edge(START, "classifier")
    workflow.add_edge("classifier", "prioritizer")
    workflow.add_edge("prioritizer", "tagger")

    # === Условные переходы ===
    workflow.add_conditional_edges("tagger", route_after_tagger, ["alert", "saver"])

    workflow.add_conditional_edges("alert", route_after_alert, ["saver"])

    # Завершение
    workflow.add_edge("saver", END)

    return workflow.compile(checkpointer=checkpointer)
