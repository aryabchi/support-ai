"""Qdrant retrieval for RAG follow-up dialog."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.agent.rag.embeddings import embed_texts
from app.config import get_settings
from app.logging_config import logger

VALID_CATEGORIES = frozenset({"technical", "billing", "feature", "other"})


@dataclass(frozen=True)
class RagChunk:
    """Один найденный чанк документа."""

    source_path: str
    text: str
    score: float | None = None


@lru_cache(maxsize=1)
def _get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    url = str(settings.QDRANT_URL).rstrip("/")
    return QdrantClient(url=url)


def retrieve(
    query_text: str,
    category: str,
    top_k: int | None = None,
) -> list[RagChunk]:
    """
    Семантический поиск по коллекции Qdrant с фильтром category.

    При ошибке или пустом запросе возвращает [] и пишет warning в лог
    (fallback на ungrounded chat на стороне вызывающего кода).
    """
    settings = get_settings()
    limit = top_k if top_k is not None else settings.RAG_TOP_K

    if not query_text or not query_text.strip():
        logger.warning("RAG retrieve: пустой query_text, возвращаем []")
        return []

    if category not in VALID_CATEGORIES:
        logger.warning(
            f"RAG retrieve: неизвестная category={category!r}, возвращаем []"
        )
        return []

    try:
        vectors = embed_texts([query_text.strip()])
        if not vectors:
            logger.warning("RAG retrieve: embed_texts вернул пустой результат")
            return []

        client = _get_qdrant_client()
        response = client.query_points(
            collection_name=settings.QDRANT_COLLECTION,
            query=vectors[0],
            query_filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="category",
                        match=qmodels.MatchValue(value=category),
                    )
                ]
            ),
            limit=limit,
            with_payload=True,
        )

        chunks: list[RagChunk] = []
        for point in response.points:
            payload = point.payload or {}
            source_path = payload.get("source_path")
            text = payload.get("text")
            if not source_path or not text:
                continue
            chunks.append(
                RagChunk(
                    source_path=str(source_path),
                    text=str(text),
                    score=float(point.score) if point.score is not None else None,
                )
            )

        logger.info(
            f"RAG retrieve: category={category}, hits={len(chunks)}, top_k={limit}"
        )
        return chunks

    except Exception as exc:
        logger.warning(
            f"RAG retrieve failed (fallback to ungrounded chat): {exc}",
            exc_info=True,
        )
        return []
