"""
Скрипт тестирования подключения к БД и базовых операций.
Запуск: python scripts/test_db.py
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в Python path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    print(f"Добавили {str(project_root)} в Python path")
    sys.path.insert(0, str(project_root))

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import *
from app.db.session import get_session_factory


async def test_connection():
    """Проверка подключения и базовой вставки/чтения."""
    try:
        factory = get_session_factory()

        async with factory() as session:
            # Простой запрос для проверки подключения
            _ = await session.scalar(text("SELECT 1"))
            print("Подключение к БД: успешно")

            # Тестовая вставка (не коммитим, чтобы не засорять БД)
            test_ticket = Ticket(
                thread_id="test_session_123",
                user_input="Тестовая заявка",
                category="technical",
                priority=TicketPriority.LOW,
                status=TicketStatus.NEW,
            )
            session.add(test_ticket)
            await session.flush()  # Получаем id, но не коммитим
            print(f"Создание объекта Ticket: id={test_ticket.id}")

            # Тестовое чтение
            ticket = await session.scalar(
                select(Ticket).where(Ticket.id == test_ticket.id)
            )
            if ticket:
                print(f"Чтение объекта Ticket: {ticket}")
            else:
                print("Не удалось прочитать созданный объект")

            # Откатываем тестовые изменения
            await session.rollback()
            print("Тестовые изменения откатаны")

        return True

    except SQLAlchemyError as e:
        print(f"Ошибка БД: {e}")
        return False
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        return False


async def main():
    print("Тестирование подключения к БД...\n")

    success = await test_connection()

    print()
    if success:
        print("Database PASS")
        return 0
    else:
        print("Database FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
