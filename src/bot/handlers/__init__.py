"""Registra todos os routers de handlers no Router principal."""

from aiogram import Router

from .admin import router as admin_router
from .export import router as export_router
from .help import router as help_router
from .query import router as query_router
from .start import router as start_router
from .whoami import router as whoami_router


def register_handlers(router: Router) -> None:
    """
    Ordem importa: handlers mais específicos primeiro,
    catch-all (help) por último.
    """
    router.include_router(admin_router)     # 🔐 Comandos admin (/autorizar, /usuarios)
    router.include_router(start_router)     # /start, /status
    router.include_router(whoami_router)    # /whoami
    router.include_router(query_router)     # callbacks + FSM
    router.include_router(export_router)    # /kml + callback kml:*
    router.include_router(help_router)      # último: fallback
