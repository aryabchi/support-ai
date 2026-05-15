import re
import unicodedata
from typing import Final

# === Константы ===

# Максимальная длина пользовательского ввода (защита от переполнения контекста)
MAX_INPUT_LENGTH: Final[int] = 10000

# Паттерны, указывающие на попытку prompt injection
BLOCKED_PATTERNS: Final[list[str]] = [
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "system instruction",
    "admin access",
    "administrator",
    "bypass security",
    "override instructions",
    "ты теперь",
    "представь что ты",
    "игнорируй инструкции",
]


def sanitize_input(text: str, max_length: int = MAX_INPUT_LENGTH) -> str:
    """
    Очищает пользовательский ввод от потенциально опасных символов.

    Что делает:
    - Обрезает длину до max_length
    - Удаляет управляющие символы (кроме \n и \t)
    - Нормализует Unicode (приводит похожие символы к единому виду)
    - Удаляет нулевые символы и невидимые разделители

    Args:
        text: Исходный текст
        max_length: Максимальная длина

    Returns:
        Очищенный текст
    """
    if not text:
        return ""

    # 1. Обрезаем длину
    text = text[:max_length]

    # 2. Нормализуем Unicode (NFKC приводит похожие символы к единому виду)
    text = unicodedata.normalize("NFKC", text)

    # 3. Удаляем управляющие символы (кроме \n, \t, \r)
    text = "".join(
        char for char in text if unicodedata.category(char) != "Cc" or char in "\n\t\r"
    )

    # 4. Удаляем нулевые символы и невидимые разделители
    text = text.replace("\x00", "")
    text = re.sub(r"[\u200b-\u200f\u2028-\u202f]", "", text)

    # 5. Обрезаем пробелы по краям
    text = text.strip()

    return text


def check_for_injection(text: str) -> bool:
    """
    Проверяет текст на наличие паттернов prompt injection.

    Args:
        text: Текст для проверки

    Returns:
        True если обнаружены подозрительные паттерны
    """
    if not text:
        return False

    text_lower = text.lower()

    for pattern in BLOCKED_PATTERNS:
        if pattern in text_lower:
            return True

    return False


def validate_input_length(
    text: str, max_length: int = MAX_INPUT_LENGTH
) -> tuple[bool, str]:
    """
    Проверяет длину ввода.

    Args:
        text: Текст для проверки
        max_length: Максимальная допустимая длина

    Returns:
        Кортеж (валидно, сообщение об ошибке)
    """
    if not text:
        return False, "Пустой ввод"

    if len(text) > max_length:
        return False, f"Превышена максимальная длина ({len(text)}/{max_length})"

    return True, ""
