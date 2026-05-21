"""
Módulo principal do bot Telegram.
"""

from src.bot.application import (
    create_bot,
    create_dispatcher,
    on_shutdown,
    on_startup,
)

__all__ = [
    "create_bot",
    "create_dispatcher",
    "on_startup",
    "on_shutdown",
]
