from sqlalchemy import text, select, func
from fastapi import APIRouter, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta

from app.db.models import Ticket
from app.logging_config import logger
from app.db.session import get_db_session

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check():
    """
    Базовая проверка доступности сервиса.
    Используется для health checks в Kubernetes/load balancer.
    """
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db_session)):
    """
    Проверка готовности сервиса принимать запросы.
    Проверяет подключение к БД.
    """
    try:
        await db.execute(text("SELECT 1"))

        logger.debug("Health check: БД доступна")

        return {
            "status": "ready",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {"database": "ok"},
        }
    except Exception as e:
        logger.error(f"Health check: БД недоступна - {e}")

        return {
            "status": "not_ready",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {"database": f"error: {str(e)}"},
        }, status.HTTP_503_SERVICE_UNAVAILABLE


@router.get("/metrics")
async def metrics_check(db: AsyncSession = Depends(get_db_session)):
    """
    Расширенные метрики системы.
    Используется для мониторинга и дашбордов.
    """
    try:
        # Число заявок (uncomment: за последние 24 часа)
        # cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        result = await db.execute(
            select(func.count(Ticket.id))  # .where(Ticket.created_at >= cutoff)
        )
        tickets_24h = result.scalar()

        # Число заявок по приоритетам
        result = await db.execute(
            select(Ticket.priority, func.count(Ticket.id)).group_by(Ticket.priority)
        )
        by_priority = {row[0]: row[1] for row in result.all()}

        return {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": {"tickets_24h": tickets_24h, "by_status": by_priority},
        }
    except Exception as e:
        logger.error(f"Metrics check failed: {e}")

        return {
            "status": "degraded",
            "error": str(e),
        }, status.HTTP_503_SERVICE_UNAVAILABLE
