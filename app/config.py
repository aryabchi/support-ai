from functools import lru_cache
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

from pydantic import (
    Field,
    PostgresDsn,
    AnyHttpUrl,
)

# custom csv parser func
# def parse_comma_separated(v: Any) -> list[str]:
#     if isinstance(v, str):
#         return [item.strip() for item in v.split(",")]
#     return v


# custom annotation for csv env vars
# CommaSeparatedList = Annotated[
#     list[str], NoDecode, BeforeValidator(parse_comma_separated)
# ]


class Settings(BaseSettings):
    """
    Настройки приложения, загружаемые из переменных окружения.

    Pydantic автоматически:
    - Загружает значения из .env файла
    - Валидирует типы и форматы
    - Предоставляет дефолтные значения
    - Даёт автодополнение в IDE
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Игнорировать неизвестные переменные
    )

    # === База данных ===
    DATABASE_URL: PostgresDsn = Field(description="URL подключения к PostgreSQL")

    # === Ollama / LLM ===
    OLLAMA_BASE_URL: AnyHttpUrl = Field(description="Базовый URL API Ollama")

    LLM_MODEL: str = Field(description="Имя модели для генерации")

    LLM_TEMPERATURE: float = Field(
        default=0.1, ge=0.0, le=1.0, description="Температура генерации (0.0-1.0)"
    )

    LLM_MAX_TOKENS: int = Field(
        default=2048, gt=0, description="Максимальное число токенов в ответе"
    )

    # === LangSmith ===
    LANGSMITH_TRACING: bool = Field(
        default=False, description="Включить трейсинг в LangSmith"
    )

    LANGSMITH_API_KEY: str | None = Field(
        default=None, description="API ключ LangSmith"
    )

    LANGSMITH_PROJECT: str = Field(
        default="support-ai", description="Имя проекта в LangSmith"
    )

    LANGSMITH_WORKSPACE_ID: str | None = Field(
        default=None, description="Рабочее пространство LangSmith"
    )

    LANGSMITH_ENDPOINT: str | None = Field(
        default=None, description="Эндпоинт для трейсинга LangSmith"
    )

    # === Приложение ===
    APP_HOST: str = Field(default="0.0.0.0")
    APP_PORT: int = Field(default=8080, gt=0, lt=65536)
    APP_ENV: str = Field(default="dev", pattern="^(dev|prod)$")

    SECRET_KEY: str = Field(
        ..., min_length=32, description="Секретный ключ для токенов (мин. 32 символа)"
    )

    # === Безопасность ===
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Разрешённые CORS источники",
    )

    RATE_LIMIT_PER_MINUTE: int = Field(
        default=60, gt=0, description="Лимит запросов в минуту на пользователя"
    )
    # === Telegram (алерты для критичных заявок) ===
    # Токен бота от @BotFather
    TELEGRAM_BOT_TOKEN: str | None

    # Chat ID пользователя/канала для получения уведомлений
    # Получите через @userinfobot
    TELEGRAM_CHAT_ID: str | None

    # === Свойства для удобства ===
    @property
    def is_dev(self) -> bool:
        """Возвращает True, если приложение запущено в режиме разработки."""
        return self.APP_ENV == "dev"

    @property
    def ollama_model_url(self) -> str:
        """Полный URL для вызова модели в Ollama."""
        return f"{self.OLLAMA_BASE_URL}/api/generate"


@lru_cache
def get_settings() -> Settings:
    """
    Возвращает кэшированный экземпляр настроек.

    lru_cache гарантирует, что настройки загружаются один раз
    и переиспользуются во всём приложении.
    """
    return Settings()
