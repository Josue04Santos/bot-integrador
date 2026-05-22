"""
Middleware de autorização (whitelist) + atualização de last_seen_at.

Responsabilidades:
    1. Bloquear usuários ausentes da tabela authorized_users
    2. Bloquear usuários com active=False
    3. Atualizar last_seen_at dos autorizados
    4. Injetar AuthorizedUser em data["auth_user"] para handlers usarem
"""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from sqlalchemy import select

from src.database.connection import db
from src.database.models import AuthorizedUser, utcnow
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AuthMiddleware(BaseMiddleware):
    """Whitelist + telemetria de presença."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Só intercepta Messages (callbacks, edits etc. passam direto)
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        tg_id = event.from_user.id

        async with db.session() as session:
            stmt = select(AuthorizedUser).where(AuthorizedUser.tg_id == tg_id)
            result = await session.execute(stmt)
            auth_user = result.scalar_one_or_none()

            # 🚫 Não cadastrado
            if auth_user is None:
                logger.warning(
                    "Acesso negado: usuário não cadastrado",
                    tg_id=tg_id,
                    username=event.from_user.username,
                )
                await event.answer(
                    "🚫 <b>Acesso negado</b>\n\n"
                    f"Seu ID Telegram (<code>{tg_id}</code>) não está autorizado.\n"
                    "Solicite acesso ao administrador."
                )
                return  # interrompe a chain

            # 🚫 Inativo
            if not auth_user.active:
                logger.warning("Acesso negado: usuário inativo", tg_id=tg_id)
                await event.answer(
                    "🚫 <b>Acesso suspenso</b>\n\n"
                    "Sua conta foi desativada. Contate o administrador."
                )
                return

            # ✅ OK — atualiza presença e injeta no contexto
            auth_user.last_seen_at = utcnow()
            # session.commit() é automático no __aexit__ do context manager

            # Atalho útil: passar dados básicos sem segurar a sessão aberta
            data["auth_user_id"] = auth_user.id
            data["auth_user_role"] = auth_user.role
            data["auth_user_full_name"] = auth_user.full_name

        return await handler(event, data)
