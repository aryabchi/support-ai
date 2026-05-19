"""
Тест логирования.
Запуск: python scripts/test_logging.py
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.logging_config import logger


def test_logging_levels():
    """Тестирует различные уровни логирования."""
    print("Тест уровней логирования...\n")

    logger.debug("DEBUG сообщение (видно только в dev режиме)")
    logger.info("INFO сообщение")
    logger.warning("WARNING сообщение")
    logger.error("ERROR сообщение")

    try:
        raise ValueError("Тестовая ошибка")
    except Exception:
        logger.exception("EXCEPTION с traceback")

    print("\nЛоги записаны (проверьте консоль)")
    return True


def test_structured_logging():
    """Тестирует структурированное логирование с extra полями."""
    print("\nТест структурированного логирования...\n")

    logger.info(
        "Тестовое событие",
        extra={"thread_id": "test_001", "category": "technical", "elapsed_ms": 123.45},
    )

    print("Структурированный лог записан")
    return True


def main():
    print("Тестирование логирования...\n")

    try:
        test_logging_levels()
        test_structured_logging()

        print("PASS")
        return 0

    except Exception as e:
        print(f"FAIL: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
