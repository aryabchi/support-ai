import logging
from functools import wraps
from typing import Callable, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


def with_llm_retry(
    max_attempts: int = 3,
    initial_wait: float = 1.0,
    max_wait: float = 10.0,
    retry_exceptions: tuple = (ConnectionError, TimeoutError),
):
    """
    Декоратор для автоматических повторных попыток при вызовах LLM.

    Args:
        max_attempts: Максимальное число попыток (по умолчанию 3)
        initial_wait: Начальная задержка в секундах
        max_wait: Максимальная задержка в секундах
        retry_exceptions: Типы исключений, при которых делать retry

    Returns:
        Декорированную функцию

    Поведение:
        - При успехе: возвращает результат функции
        - При исчерпании попыток: поднимает RetryError
        - При других ошибках: поднимает исключение
    """

    def decorator(func: Callable) -> Callable:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=initial_wait, max=max_wait),
            retry=retry_if_exception_type(retry_exceptions),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        def _retryable(*args, **kwargs):
            return func(*args, **kwargs)

        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return _retryable(*args, **kwargs)

        return wrapper

    return decorator
