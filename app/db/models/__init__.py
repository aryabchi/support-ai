"""
Центральный импорт всех моделей.

Импорт этого модуля гарантирует, что все модели зарегистрированы
в метаданных Base до начала работы с БД.
"""

from .history import TicketHistory
from .ticket import Ticket, TicketPriority, TicketStatus

# Экспортируем для удобства
__all__ = ["Ticket", "TicketPriority", "TicketStatus", "TicketHistory"]
