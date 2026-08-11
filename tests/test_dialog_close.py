"""
Unit-тесты детекции закрытия диалога (goodbye / success / escalate).
Запуск: pytest tests/test_dialog_close.py -v
"""

import sys
from pathlib import Path
from unittest.mock import patch

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.agent.state import AgentState
from app.agent.nodes.chat_handler import (
    SUCCESS_CLOSE_RESPONSE,
    ESCALATE_CLOSE_RESPONSE,
    _detect_close_reason,
    _is_goodbye_message,
    _is_success_close,
    _is_escalate_message,
    _normalize_user_message,
    chat_handler,
)


def _mock_llm_response(text: str):
    from unittest.mock import Mock

    mock_response = Mock()
    mock_response.content = text
    return mock_response


class TestNormalizeAndHelpers:
    def test_normalize_strips_and_lowers(self):
        assert _normalize_user_message("  Спасибо!  ") == "спасибо!"

    def test_goodbye_words_only(self):
        assert _is_goodbye_message("пока") is True
        assert _is_goodbye_message("до свидания") is True
        assert _is_goodbye_message("спасибо, пока!") is True
        assert _is_goodbye_message("спасибо, помогло!") is False

    def test_success_close_phrases(self):
        assert _is_success_close("спасибо") is True
        assert _is_success_close("помогло") is True
        assert _is_success_close("спасибо, помогло!") is True
        assert _is_success_close("спасибо, пока!") is False
        assert _is_success_close("спасибо, а пароль?") is False
        assert _is_success_close("спасибо " + ("а" * 50)) is False

    def test_escalate_keywords(self):
        assert _is_escalate_message("хочу оператора") is True
        assert _is_escalate_message("нужна поддержка") is True
        assert _is_escalate_message("это не помогло") is True
        assert _is_escalate_message("перезвоните мне") is True
        assert _is_escalate_message("ошибка 401") is False


class TestDetectCloseReasonOrder:
    def test_escalate_before_success(self):
        # содержит и «не помог», и «спасибо» — escalate первым
        assert (
            _detect_close_reason("спасибо, но не помогло, нужен оператор")
            == "escalate"
        )

    def test_thanks_with_goodbye_is_goodbye_not_success(self):
        assert _detect_close_reason("спасибо, пока!") == "goodbye"

    def test_thanks_helped_is_success(self):
        assert _detect_close_reason("спасибо, помогло!") == "success"

    def test_question_after_thanks_is_none(self):
        assert _detect_close_reason("спасибо, а пароль?") is None

    def test_plain_goodbye(self):
        assert _detect_close_reason("пока") == "goodbye"


class TestChatHandlerClosePaths:
    @patch("app.agent.nodes.chat_handler._chat_llm_call")
    def test_success_close_sets_dialog_closed(self, mock_llm):
        state = AgentState(thread_id="t1", user_input="Спасибо, помогло!")
        result = chat_handler(state)

        assert result["dialog_closed"] is True
        assert result["close_reason"] == "success"
        assert result["last_response"] == SUCCESS_CLOSE_RESPONSE
        mock_llm.assert_not_called()

    @patch("app.agent.nodes.chat_handler._chat_llm_call")
    def test_goodbye_with_thanks_is_goodbye(self, mock_llm):
        mock_llm.return_value = _mock_llm_response("Всего доброго!")

        state = AgentState(thread_id="t1", user_input="Спасибо, пока!")
        result = chat_handler(state)

        assert result["dialog_closed"] is True
        assert result["close_reason"] == "goodbye"
        mock_llm.assert_called_once()

    @patch("app.agent.nodes.chat_handler._chat_llm_call")
    def test_escalate_sets_dialog_closed(self, mock_llm):
        state = AgentState(thread_id="t1", user_input="Хочу оператора")
        result = chat_handler(state)

        assert result["dialog_closed"] is True
        assert result["close_reason"] == "escalate"
        assert result["last_response"] == ESCALATE_CLOSE_RESPONSE
        mock_llm.assert_not_called()

    @patch("app.agent.nodes.chat_handler._chat_llm_call")
    def test_thanks_with_question_continues_chat(self, mock_llm):
        mock_llm.return_value = _mock_llm_response("Какой именно пароль?")

        state = AgentState(thread_id="t1", user_input="Спасибо, а пароль?")
        result = chat_handler(state)

        assert result.get("dialog_closed") is not True
        assert "close_reason" not in result
        mock_llm.assert_called_once()
