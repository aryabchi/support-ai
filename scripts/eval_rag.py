"""
Offline RAG eval: retrieval smoke + optional ragas metrics on fake corpus.

Не входит в default pytest. Нужны:
  - Qdrant с инжестом (python scripts/ingest_rag_docs.py)
  - Ollama (тот же LLM, что у приложения) для LLM-as-judge метрик ragas

Запуск из корня репозитория (venv ai-course):
    python scripts/eval_rag.py
    python scripts/eval_rag.py --retrieval-only
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.agent.rag.retriever import retrieve
from app.config import get_settings
from app.logging_config import logger


@dataclass(frozen=True)
class EvalCase:
    """Один кейс на основе data/rag_docs."""

    question: str
    category: str
    tags: tuple[str, ...]
    reference: str
    expected_source_substr: str


# Мини-набор по четырём категориям корпуса (ground truth ≈ текст доков).
EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        question="Что делать при ошибке 401 Unauthorized при входе?",
        category="technical",
        tags=("login", "401"),
        reference=(
            "При ошибке 401 проверьте логин и пароль без лишних пробелов, "
            "раскладку и Caps Lock, сбросьте пароль через «Забыли пароль?», "
            "очистите cookies или попробуйте инкогнито. Если не помогло — "
            "напишите в поддержку с временем попытки входа."
        ),
        expected_source_substr="login_error_401",
    ),
    EvalCase(
        question="В какой срок можно оформить возврат средств?",
        category="billing",
        tags=("refund", "оплата"),
        reference=(
            "Возврат возможен в течение 14 дней после оплаты, если услугой "
            "почти не пользовались. Заявка: Настройки → Подписка → "
            "«Запросить возврат»; решение на email за 3 рабочих дня."
        ),
        expected_source_substr="refund_policy",
    ),
    EvalCase(
        question="Можно ли выгрузить отчёты в CSV?",
        category="feature",
        tags=("export", "csv"),
        reference=(
            "Сейчас доступен экспорт в PDF из раздела «Отчёты». CSV-экспорт "
            "планируется для списка задач и истории платежей. Пока можно "
            "скопировать таблицу вручную или запросить выгрузку у поддержки."
        ),
        expected_source_substr="export_csv",
    ),
    EvalCase(
        question="Как удалить аккаунт и персональные данные?",
        category="other",
        tags=("account", "delete"),
        reference=(
            "Настройки → Аккаунт → «Удалить аккаунт», подтвердите паролем и "
            "кодом из email. Данные удаляются в течение 30 дней. Экспортируйте "
            "нужные данные заранее."
        ),
        expected_source_substr="delete_account",
    ),
)


def _probe_qdrant() -> None:
    """Проверяет доступность Qdrant и наличие коллекции."""
    from qdrant_client import QdrantClient

    settings = get_settings()
    client = QdrantClient(url=str(settings.QDRANT_URL).rstrip("/"))
    names = {c.name for c in client.get_collections().collections}
    if settings.QDRANT_COLLECTION not in names:
        raise RuntimeError(
            f"Коллекция {settings.QDRANT_COLLECTION!r} не найдена в Qdrant. "
            "Сначала выполните: python scripts/ingest_rag_docs.py"
        )


def _build_query(question: str, tags: tuple[str, ...]) -> str:
    parts = [question.strip()]
    if tags:
        parts.append(" ".join(tags))
    return " ".join(parts).strip()


def _run_retrieval_smoke(cases: tuple[EvalCase, ...]) -> list[dict]:
    """
    Retrieval smoke без ragas: ожидаемый source_path должен попасть в hits.

    Returns list of row dicts for ragas (user_input, retrieved_contexts, ...).
    """
    rows: list[dict] = []
    failed = 0

    for case in cases:
        query = _build_query(case.question, case.tags)
        chunks = retrieve(query, case.category)
        contexts = [c.text for c in chunks]
        paths = [c.source_path for c in chunks]
        hit = any(case.expected_source_substr in p for p in paths)

        status = "OK" if hit and contexts else "MISS"
        if status != "OK":
            failed += 1

        print(
            f"[{status}] category={case.category} "
            f"expected~={case.expected_source_substr!r} hits={len(chunks)} "
            f"paths={paths}"
        )

        # response = reference: faithfulness/context_* оценивают, насколько
        # retrieve покрывает известный ответ из fake docs.
        rows.append(
            {
                "user_input": case.question,
                "retrieved_contexts": contexts,
                "response": case.reference,
                "reference": case.reference,
            }
        )

    if failed:
        raise RuntimeError(
            f"Retrieval smoke failed: {failed}/{len(cases)} cases missed "
            "expected source. Проверьте ingest и корпус data/rag_docs."
        )

    print(f"Retrieval smoke: {len(cases)}/{len(cases)} OK")
    return rows


def _run_ragas(rows: list[dict]) -> None:
    """LLM-as-judge метрики ragas (Ollama + MiniLM embeddings)."""
    from datasets import Dataset
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from ragas import evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )
    from ragas.run_config import RunConfig

    from app.agent.llm import llm

    settings = get_settings()
    dataset = Dataset.from_list(rows)
    embeddings = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name=settings.RAG_EMBED_MODEL)
    )

    print(
        "Running ragas metrics (faithfulness, context_precision, "
        "context_recall, answer_relevancy) via Ollama judge..."
    )
    result = evaluate(
        dataset,
        metrics=[
            faithfulness,
            context_precision,
            context_recall,
            answer_relevancy,
        ],
        llm=llm,
        embeddings=embeddings,
        raise_exceptions=False,
        batch_size=1,
        run_config=RunConfig(timeout=600, max_workers=1),
    )
    print(result)

    scores = dict(result) if hasattr(result, "keys") else {}
    if scores and all(
        (v != v)  # NaN
        for v in scores.values()
        if isinstance(v, float)
    ):
        print(
            "WARN: все ragas-метрики NaN (часто TimeoutError у Ollama judge). "
            "Retrieval smoke уже пройден; повторите при доступном Ollama "
            "или используйте --retrieval-only.",
            file=sys.stderr,
        )
        return

    try:
        print(result.to_pandas().to_string(index=False))
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline RAG eval (ragas + fake docs)")
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Только smoke retrieve по expected source_path (без ragas/Ollama)",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    print(
        f"Qdrant={settings.QDRANT_URL} collection={settings.QDRANT_COLLECTION} "
        f"top_k={settings.RAG_TOP_K} embed={settings.RAG_EMBED_MODEL}"
    )

    try:
        _probe_qdrant()
    except Exception as exc:
        logger.error(f"eval_rag: Qdrant unavailable — {exc}")
        print(
            "SKIP: Qdrant/collection недоступны. "
            "Поднимите Qdrant и выполните ingest, затем повторите.",
            file=sys.stderr,
        )
        return 2

    try:
        rows = _run_retrieval_smoke(EVAL_CASES)
    except Exception as exc:
        logger.error(f"eval_rag: retrieval smoke failed — {exc}")
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    if args.retrieval_only:
        print("Done (--retrieval-only).")
        return 0

    try:
        _run_ragas(rows)
    except Exception as exc:
        logger.warning(f"eval_rag: ragas skipped/failed — {exc}", exc_info=True)
        print(
            f"WARN: retrieval smoke OK, но ragas не завершился: {exc}\n"
            "Проверьте Ollama и зависимости ragas. "
            "Для smoke без LLM: python scripts/eval_rag.py --retrieval-only",
            file=sys.stderr,
        )
        return 0

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
