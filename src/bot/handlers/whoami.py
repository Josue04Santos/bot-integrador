"""
Handler /whoami — devolve identificação do usuário atual.
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="whoami")


@router.message(Command("whoami"))
async def cmd_whoami(
    message: Message,
    auth_user_id: str,
    auth_user_role: str,
    auth_user_full_name: str | None,
) -> None:
    """
    Mostra ID, role e nome do usuário autenticado.
    Útil para debug e para o usuário confirmar que está autorizado.
    """
    user = message.from_user
    logger.info("/whoami", tg_id=user.id, role=auth_user_role)

    text = (
        "👤 <b>Sua identidade</b>\n\n"
        f"<b>Nome:</b> {auth_user_full_name or user.first_name}\n"
        f"<b>Username:</b> @{user.username or '<i>sem username</i>'}\n"
        f"<b>Telegram ID:</b> <code>{user.id}</code>\n"
        f"<b>User ID (interno):</b> <code>{auth_user_id}</code>\n"
        f"<b>Role:</b> <code>{auth_user_role}</code>\n"
        f"<b>Idioma:</b> <code>{user.language_code or 'n/a'}</code>"
    )

    await message.answer(text)
