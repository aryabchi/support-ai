import sys
import logging
from app.config import get_settings
from pythonjsonlogger import jsonlogger


def setup_logging():
    """
    Настраивает централизованное логирование для приложения.

    В режиме dev:
    - Вывод в консоль с читаемым форматом
    - Уровень DEBUG

    В режиме prod:
    - Вывод в консоль в JSON-формате (для сбора логами)
    - Уровень INFO
    """
    settings = get_settings()

    # Создаём logger для приложения
    logger = logging.getLogger("support_ai")
    logger.setLevel(logging.DEBUG if settings.is_dev else logging.INFO)

    # Очищаем существующие обработчики
    logger.handlers = []

    # Создаём обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)

    if settings.is_dev:
        # Dev: читаемый формат для отладки
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        # Prod: JSON-формат для агрегации (ELK, CloudWatch, etc.)
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )

    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG if settings.is_dev else logging.INFO)
    logger.addHandler(console_handler)

    # Запрещаем propagate, чтобы не дублировать логи в root logger
    logger.propagate = False

    return logger


# Глобальный экземпляр logger
logger = setup_logging()
