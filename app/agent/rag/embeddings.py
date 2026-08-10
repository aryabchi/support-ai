"""Lazy SentenceTransformer embeddings for RAG ingest and retrieval."""

from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import get_settings
from app.logging_config import logger


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    """
    Возвращает кэшированный SentenceTransformer.
    Модель загружается при первом вызове (может скачать веса с HuggingFace).
    """
    settings = get_settings()
    model_name = settings.RAG_EMBED_MODEL
    logger.info(f"Загрузка embedding-модели: {model_name}")
    return SentenceTransformer(model_name)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Строит эмбеддинги для списка текстов.

    Returns:
        Список векторов (каждый — list[float], размерность модели, для MiniLM — 384).
    """
    if not texts:
        return []

    model = get_embedder()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [vector.tolist() for vector in vectors]
