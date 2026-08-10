"""
Инжест локального корпуса data/rag_docs в Qdrant.

Пайплайн: validate → chunk → embed → upsert (идемпотентно).

Запуск (из корня репозитория, venv ai-course):
    python scripts/ingest_rag_docs.py
"""

from __future__ import annotations

import hashlib
import sys
import uuid
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.agent.rag.embeddings import embed_texts
from app.config import get_settings
from app.logging_config import logger

VALID_CATEGORIES = frozenset({"technical", "billing", "feature", "other"})
CHUNK_SIZE = 450
CHUNK_OVERLAP = 50
VECTOR_SIZE = 384


def _point_id(source_path: str, chunk_index: int) -> str:
    """Детерминированный UUID для идемпотентного upsert."""
    digest = hashlib.sha256(f"{source_path}::{chunk_index}".encode()).hexdigest()
    return str(uuid.UUID(digest[:32]))


def _collect_documents(docs_root: Path) -> list[tuple[str, str, str]]:
    """
    Собирает (category, source_path, text) из markdown-файлов.

    category = имя родительской папки; source_path — относительно docs_root.
    """
    if not docs_root.is_dir():
        raise FileNotFoundError(f"Каталог корпуса не найден: {docs_root}")

    documents: list[tuple[str, str, str]] = []
    for path in sorted(docs_root.rglob("*.md")):
        category = path.parent.name
        if category not in VALID_CATEGORIES:
            logger.warning(f"Пропуск {path}: категория '{category}' не из {VALID_CATEGORIES}")
            continue

        text = path.read_text(encoding="utf-8").strip()
        if not text:
            logger.warning(f"Пропуск пустого файла: {path}")
            continue

        source_path = path.relative_to(docs_root).as_posix()
        documents.append((category, source_path, text))

    return documents


def _chunk_documents(
    documents: list[tuple[str, str, str]],
) -> list[tuple[str, str, int, str]]:
    """Возвращает (category, source_path, chunk_index, chunk_text)."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
    )
    chunks: list[tuple[str, str, int, str]] = []
    for category, source_path, text in documents:
        parts = splitter.split_text(text)
        if not parts:
            logger.warning(f"Нет чанков для {source_path}")
            continue
        for index, part in enumerate(parts):
            chunk_text = part.strip()
            if chunk_text:
                chunks.append((category, source_path, index, chunk_text))
    return chunks


def _ensure_collection(client: QdrantClient, collection_name: str) -> None:
    """Создаёт коллекцию, если её ещё нет (cosine, 384-d)."""
    existing = {c.name for c in client.get_collections().collections}
    if collection_name in existing:
        logger.info(f"Коллекция уже существует: {collection_name}")
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=qmodels.VectorParams(
            size=VECTOR_SIZE,
            distance=qmodels.Distance.COSINE,
        ),
    )
    logger.info(f"Создана коллекция: {collection_name} (size={VECTOR_SIZE}, cosine)")


def ingest() -> int:
    settings = get_settings()
    docs_root = (project_root / settings.RAG_DOCS_PATH).resolve()
    collection = settings.QDRANT_COLLECTION
    qdrant_url = str(settings.QDRANT_URL).rstrip("/")

    logger.info(f"Инжест из {docs_root} -> {qdrant_url}/{collection}")

    documents = _collect_documents(docs_root)
    if not documents:
        logger.error("Нет документов для инжеста")
        return 1

    chunks = _chunk_documents(documents)
    if not chunks:
        logger.error("После чанкинга нет точек для upsert")
        return 1

    logger.info(f"Документов: {len(documents)}, чанков: {len(chunks)}")

    texts = [c[3] for c in chunks]
    vectors = embed_texts(texts)
    if len(vectors) != len(chunks):
        logger.error(
            f"Число векторов ({len(vectors)}) не совпадает с числом чанков ({len(chunks)})"
        )
        return 1
    if vectors and len(vectors[0]) != VECTOR_SIZE:
        logger.error(f"Ожидалась размерность {VECTOR_SIZE}, получено {len(vectors[0])}")
        return 1

    client = QdrantClient(url=qdrant_url)
    _ensure_collection(client, collection)

    points = [
        qmodels.PointStruct(
            id=_point_id(source_path, chunk_index),
            vector=vector,
            payload={
                "category": category,
                "source_path": source_path,
                "text": chunk_text,
            },
        )
        for (category, source_path, chunk_index, chunk_text), vector in zip(
            chunks, vectors, strict=True
        )
    ]

    client.upsert(collection_name=collection, points=points)

    info = client.get_collection(collection)
    point_count = info.points_count
    logger.info(
        f"Upsert завершён: записано {len(points)} точек, "
        f"в коллекции сейчас points_count={point_count}"
    )
    return 0


def main() -> None:
    try:
        raise SystemExit(ingest())
    except Exception:
        logger.exception("Инжест завершился с ошибкой")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
