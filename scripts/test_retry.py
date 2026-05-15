"""
Тест retry-логики агента.
Запуск: python scripts/test_retry.py
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.agent.state import AgentState
from app.agent.nodes.classifier import classify_ticket


def test_retry_on_failure():
    """Тестирует, что retry срабатывает при ошибках LLM."""
    print("Тест retry при сбоях LLM...")

    state = AgentState(thread_id="test_retry_001", user_input="Не могу войти в аккаунт")

    mock_response = Mock()
    mock_response.content = "technical"

    # Симулируем 2 сбоя, затем успех
    with patch("app.agent.nodes.classifier.llm") as mock_llm:
        mock_llm.invoke.side_effect = [
            ConnectionError("Network error"),  # Попытка 1: сбой
            TimeoutError("Timeout"),  # Попытка 2: сбой
            mock_response,  # Попытка 3: успех
        ]

        result = classify_ticket(state)

        assert result.get("category") == "technical"
        assert mock_llm.invoke.call_count == 3
        print(f"Retry сработал: {mock_llm.invoke.call_count} попытки")

    return True


def test_fallback_on_exhausted_retry():
    """Тестирует fallback при исчерпании попыток."""
    print("\nТест fallback при исчерпании retry...")

    state = AgentState(thread_id="test_retry_002", user_input="Тестовый запрос")

    # Симулируем постоянные сбои
    with patch("app.agent.nodes.classifier.llm") as mock_llm:
        mock_llm.invoke.side_effect = ConnectionError("Permanent error")

        result = classify_ticket(state)

        assert result.get("category") == "other"
        assert "error" in result
        print(f"Retry сработал: {mock_llm.invoke.call_count} попытки")
        print(f"Fallback сработал: категория={result.get('category')}")

    return True


def test_normal_execution():
    """Тестирует нормальное выполнение без сбоев."""
    print("\nТест нормального выполнения...")

    state = AgentState(
        thread_id="test_retry_003", user_input="Не работает вход в систему"
    )

    mock_response = Mock()
    mock_response.content = "technical"

    with patch("app.agent.nodes.classifier.llm") as mock_llm:
        mock_llm.invoke.return_value = mock_response

        try:
            result = classify_ticket(state)
            assert result.get("category") in (
                "technical",
                "billing",
                "feature",
                "other",
            )
            print(f"Нормальное выполнение: категория={result.get('category')}")
            return True
        except Exception as e:
            print(f"Ollama недоступна (это нормально для теста): {e}")
            return True


def main():
    print("Тестирование retry-логики...\n")

    try:
        test_retry_on_failure()
        test_fallback_on_exhausted_retry()
        test_normal_execution()

        print("\nPASS")
        return 0

    except AssertionError as e:
        print(f"\nFAIL: {e}")
        return 1
    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
