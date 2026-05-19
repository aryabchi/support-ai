"""
Тест восстановления состояния агента через чекпоинты.
Запуск: python scripts/test_checkpoints.py

PostgresSaver управляет своими таблицами internally — мы проверяем
чекпоинты через его API, а не через прямые SQL-запросы.
"""

import sys
import asyncio
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.config import get_settings
from app.agent.state import AgentState
from app.core.dependencies import get_agent_graph
from app.agent.checkpointer import get_checkpointer


async def test_checkpoint_persistence():
    """Проверяет, что чекпоинты сохраняются и восстанавливаются через PostgresSaver."""

    thread_id = "test_checkpoint_recovery_001"
    settings = get_settings()
    db_url = str(settings.DATABASE_URL)

    # Начальное состояние
    initial_state = AgentState(
        thread_id=thread_id, user_input="Тестовая заявка для проверки чекпоинтов"
    )
    build_graph = get_agent_graph()

    # Первый запуск: агент обрабатывает заявку и сохраняет чекпоинты
    async with get_checkpointer(db_url) as checkpointer:
        agent_graph = build_graph(checkpointer=checkpointer)

        result = await agent_graph.ainvoke(
            initial_state,
            config={
                "configurable": {
                    "thread_id": thread_id,
                }
            },
        )

    print(
        f"Первый запуск завершён: priority={result.get('priority')}, done={result.get('done')}"
    )

    # Проверяем, что чекпоинты записаны через API PostgresSaver
    async with get_checkpointer(db_url) as checkpointer:
        # Получаем последний чекпоинт для этой сессии
        config = {"configurable": {"thread_id": thread_id}}
        checkpoint_tuple = await checkpointer.aget_tuple(config)

        if checkpoint_tuple:
            print("Чекпоинт найден в БД:")
            print(
                f"   • checkpoint_id={checkpoint_tuple.config['configurable']['checkpoint_id'][:10]}..."
            )
            print(
                f"   • priority={checkpoint_tuple.checkpoint.get('channel_values', {}).get('priority', 'N/A')}"
            )
            print(
                f"   • user_input={checkpoint_tuple.checkpoint.get('channel_values', {}).get('user_input', 'N/A')}"
            )
        else:
            print("Чекпоинты не найдены в БД")
            return False

        # Проверяем историю чекпоинтов (список всех для этой сессии)
        checkpoints = [c async for c in checkpointer.alist(config, limit=10)]
        print(f"Всего чекпоинтов для сессии: {len(checkpoints)}")

    # Второй запуск с тем же thread_id: должен восстановить состояние
    async with get_checkpointer(db_url) as checkpointer:
        agent_graph = build_graph(checkpointer=checkpointer)

        # Запускаем с минимальным состоянием — чекпоинты должны восстановить контекст
        restored_result = await agent_graph.ainvoke(
            {"thread_id": thread_id},
            config={
                "configurable": {
                    "thread_id": thread_id,
                }
            },
        )

    print(
        f"Восстановленное состояние: priority={restored_result.get('priority')}\n"
        f"done={restored_result.get('done')}\n"
        f"user_input={restored_result.get('user_input')}\n"
    )

    # Проверяем, что состояние восстановлено корректно
    if restored_result.get("done") and restored_result.get("priority"):
        print("Чекпоинты работают: состояние восстановлено успешно")
        return True
    else:
        print("Состояние не восстановлено")
        return False


async def test_checkpoint_isolation():
    """Проверяет, что чекпоинты изолированы по thread_id."""

    thread_id_1 = "test_isolation_001"
    thread_id_2 = "test_isolation_002"

    settings = get_settings()
    db_url = str(settings.DATABASE_URL)
    build_graph = get_agent_graph()

    # Запускаем два разных потока с разными данными
    async with get_checkpointer(db_url) as checkpointer:
        agent_graph = build_graph(checkpointer=checkpointer)
        thread_id_1_config = {"configurable": {"thread_id": thread_id_1}}
        thread_id_2_config = {"configurable": {"thread_id": thread_id_2}}

        await agent_graph.ainvoke(
            AgentState(thread_id=thread_id_1, user_input="Запрос 1"),
            config=thread_id_1_config,
        )

        await agent_graph.ainvoke(
            AgentState(thread_id=thread_id_2, user_input="Запрос 2"),
            config=thread_id_2_config,
        )

    # Проверяем, что чекпоинты не пересеклись
    async with get_checkpointer(db_url) as checkpointer:
        checkpoints_1 = [
            c.config["configurable"]["checkpoint_id"]
            async for c in checkpointer.alist(thread_id_1_config)
        ]
        checkpoints_2 = [
            c.config["configurable"]["checkpoint_id"]
            async for c in checkpointer.alist(thread_id_2_config)
        ]
        common_checkpoints = len(set(checkpoints_1) & set(checkpoints_2))
        if common_checkpoints:
            print("найдены общие чекпоинты сессий")
            return False

        if len(checkpoints_1) > 0 and len(checkpoints_2) > 0:
            print(
                f"Изоляция сессий работает: session_1={len(checkpoints_1)} чекпоинтов, session_2={len(checkpoints_2)} чекпоинтов"
            )
            return True
        else:
            print("Изоляция сессий не работает")
            return False


async def main():
    print("Тестирование чекпоинтов...\n")

    print("Тест 1: Сохранение и восстановление состояния")
    print("-" * 50)
    test1 = await test_checkpoint_persistence()

    print("\nТест 2: Изоляция сессий по thread_id")
    print("-" * 50)
    test2 = await test_checkpoint_isolation()

    print("\n" + "=" * 50)
    if test1 and test2:
        print("PASS")
        return 0
    else:
        print("FAIL")
        return 1


if __name__ == "__main__":
    # Quick fix (the default event loop on Windows is ProactorEventLoop)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.exit(asyncio.run(main()))
