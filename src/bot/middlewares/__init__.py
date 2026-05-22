"""
Middlewares do bot Telegram.
"""

from aiogram import Dispatcher

from .auth import AuthMiddleware
from .logging import LoggingMiddleware


def setup_middlewares(dp: Dispatcher) -> None:
    """
    Configura middlewares no dispatcher.

    ORDEM (importa!):
        1. Logging → registra TUDO, inclusive tentativas bloqueadas
        2. Auth    → barra não-autorizados antes dos handlers
    """
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(AuthMiddleware())


__all__ = ["setup_middlewares", "LoggingMiddleware", "AuthMiddleware"]
