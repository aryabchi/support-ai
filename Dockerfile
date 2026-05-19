# Используем официальный образ Python 3.11 (slim — минимальный размер)
FROM python:3.11.15-bookworm

# Устанавливаем переменные окружения
# - PYTHONUNBUFFERED=1: логи выводятся в консоль сразу, без буферизации
# - PYTHONDONTWRITEBYTECODE=1: не создаём .pyc файлы
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем только requirements.txt сначала — для кэширования слоёв
COPY requirements.txt .

# Устанавливаем зависимости
# --no-cache-dir: не кэшируем пакеты, уменьшаем размер образа
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код приложения
COPY . .

# Создаём непривилегированного пользователя для безопасности
# (опционально, но рекомендуется для продакшена)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Открываем порт для FastAPI
EXPOSE 8080