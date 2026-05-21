"""
Handlers do bot Telegram.
"""

from aiogram import Router

from .start import router as start_router
from .help import router as help_router


def register_handlers(router: Router) -> None:
    """
    Registra todos os handlers no router principal.
    
    Args:
        router: Router principal do dispatcher.
    """
    router.include_router(start_router)
    router.include_router(help_router)


__all__ = ["register_handlers"]
