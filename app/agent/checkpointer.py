from contextlib import asynccontextmanager
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


@asynccontextmanager
async def get_checkpointer(db_url: str):
    """
    Context manager для AsyncPostgresSaver.

    Args:
        db_url: Строка подключения в формате postgresql+asyncpg://...

    Yields:
        Настроенный экземпляр AsyncPostgresSaver
    """
    # AsyncPostgresSaver работает с синхронным подключением внутри
    # Преобразуем asyncpg URL в формат для psycopg
    conn_url = str(db_url).replace("postgresql+asyncpg://", "postgresql://")

    # Явно разрешаем сериализацию AgentState, чтобы избежать предупреждений
    # о небезопасной десериализации произвольных классов
    serde = JsonPlusSerializer(
        allowed_msgpack_modules=[("app.agent.state", "AgentState")]
    )

    async with AsyncPostgresSaver.from_conn_string(conn_url, serde=serde) as saver:
        # setup() создаёт необходимые таблицы, если их нет:
        # - checkpoints: основные записи чекпоинтов
        # - checkpoint_blobs: большие сериализованные данные
        # - checkpoint_writes: промежуточные записи узлов
        # - checkpoint_migrations: версионирование схемы
        await saver.setup()
        yield saver
