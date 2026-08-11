"""
Unit-тесты RAG retriever (мок Qdrant и embedder).
Запуск: pytest tests/test_rag_retriever.py -v
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.agent.rag.retriever import RagChunk, retrieve, _get_qdrant_client


def _hit(source_path: str, text: str, score: float = 0.9):
    point = MagicMock()
    point.payload = {"source_path": source_path, "text": text, "category": "technical"}
    point.score = score
    return point


class TestRetrieve:
    def setup_method(self):
        _get_qdrant_client.cache_clear()

    @patch("app.agent.rag.retriever.embed_texts")
    @patch("app.agent.rag.retriever.QdrantClient")
    def test_returns_chunks_with_category_filter(self, mock_client_cls, mock_embed):
        mock_embed.return_value = [[0.1] * 384]
        client = MagicMock()
        response = MagicMock()
        response.points = [
            _hit("technical/login_error_401.md", "Ошибка 401"),
            _hit("technical/password_reset_steps.md", "Сброс пароля"),
        ]
        client.query_points.return_value = response
        mock_client_cls.return_value = client

        chunks = retrieve("ошибка 401 пароль", "technical", top_k=3)

        assert len(chunks) == 2
        assert chunks[0] == RagChunk(
            source_path="technical/login_error_401.md",
            text="Ошибка 401",
            score=0.9,
        )
        mock_embed.assert_called_once_with(["ошибка 401 пароль"])
        call_kwargs = client.query_points.call_args.kwargs
        assert call_kwargs["limit"] == 3
        assert call_kwargs["query_filter"] is not None
        must = call_kwargs["query_filter"].must
        assert must[0].key == "category"
        assert must[0].match.value == "technical"

    @patch("app.agent.rag.retriever.embed_texts")
    @patch("app.agent.rag.retriever.QdrantClient")
    def test_empty_query_returns_empty(self, mock_client_cls, mock_embed):
        assert retrieve("  ", "technical") == []
        mock_embed.assert_not_called()
        mock_client_cls.assert_not_called()

    @patch("app.agent.rag.retriever.embed_texts")
    @patch("app.agent.rag.retriever.QdrantClient")
    def test_invalid_category_returns_empty(self, mock_client_cls, mock_embed):
        assert retrieve("ошибка", "unknown") == []
        mock_embed.assert_not_called()

    @patch("app.agent.rag.retriever.embed_texts")
    @patch("app.agent.rag.retriever.QdrantClient")
    def test_qdrant_error_returns_empty(self, mock_client_cls, mock_embed):
        mock_embed.return_value = [[0.1] * 384]
        client = MagicMock()
        client.query_points.side_effect = ConnectionError("qdrant down")
        mock_client_cls.return_value = client

        chunks = retrieve("ошибка 401", "technical")

        assert chunks == []

    @patch("app.agent.rag.retriever.embed_texts")
    @patch("app.agent.rag.retriever.QdrantClient")
    def test_skips_hits_without_payload_fields(self, mock_client_cls, mock_embed):
        mock_embed.return_value = [[0.1] * 384]
        bad = MagicMock()
        bad.payload = {"category": "technical"}
        bad.score = 0.5
        response = MagicMock()
        response.points = [bad, _hit("technical/ok.md", "ok text", 0.8)]
        client = MagicMock()
        client.query_points.return_value = response
        mock_client_cls.return_value = client

        chunks = retrieve("тест", "technical")

        assert len(chunks) == 1
        assert chunks[0].source_path == "technical/ok.md"
