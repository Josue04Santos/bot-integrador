"""
Middlewares do bot Telegram.
"""

from aiogram import Dispatcher

from .logging import LoggingMiddleware


def setup_middlewares(dp: Dispatcher) -> None:
    """
    Configura todos os middlewares no dispatcher.
    
    Args:
        dp: Dispatcher do bot.
    """
    # Middleware de logging em todas as mensagens
    dp.message.middleware(LoggingMiddleware())


__all__ = ["setup_middlewares", "LoggingMiddleware"]
