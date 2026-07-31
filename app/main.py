from contextlib import asynccontextmanager

from app.api.routes import health, tickets
from app.config import get_settings
from app.db.session import get_engine
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select


# Lifespan context manager для инициализации/очистки при старте/остановке
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Инициализация при старте
    engine = get_engine()

    # Проверка подключения к БД (опционально, для раннего обнаружения проблем)
    async with engine.connect() as conn:
        await conn.execute(select(1))

    yield

    # Очистка при остановке
    await engine.dispose()


# Создание приложения с lifespan
app = FastAPI(
    title="SupportAI API",
    description="API для системы автоматической обработки заявок",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware для разрешения запросов с фронтенда
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Регистрация роутов
app.include_router(tickets.router)
app.include_router(health.router)


# Root endpoint с документацией
@app.get("/")
async def root():
    """Корневой эндпоинт с ссылками на документацию."""
    return {
        "message": "SupportAI API",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }
