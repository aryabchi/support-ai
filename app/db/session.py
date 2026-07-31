from functools import lru_cache
from typing import AsyncGenerator

from app.config import get_settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@lru_cache
def get_engine():
    """
    Создаёт и кэширует async engine для подключения к БД.

    lru_cache гарантирует, что engine создаётся один раз
    и переиспользуется во всём приложении.
    """
    settings = get_settings()

    return create_async_engine(
        str(settings.DATABASE_URL),
        pool_pre_ping=True,  # Проверка соединения перед использованием
        pool_size=10,  # Размер пула соединений
        max_overflow=20,  # Дополнительные соединения при пиковой нагрузке
        echo=settings.is_dev,  # Логирование SQL-запросов в режиме dev
    )


@lru_cache
def get_session_factory():
    """
    Создаёт и кэширует фабрику сессий.

    Возвращает async_sessionmaker, который создаёт AsyncSession.
    """
    engine = get_engine()

    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency для FastAPI: создаёт сессию на один запрос.

    Использование в эндпоинтах:
    async with get_db_session() as session:
        # работа с БД
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
