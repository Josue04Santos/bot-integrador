"""
Handler do comando /help.
"""

import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

logger = structlog.get_logger(__name__)
router = Router(name="help")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """
    Handler para o comando /help.
    Exibe lista de comandos disponíveis.
    """
    logger.info(
        "Comando /help recebido",
        user_id=message.from_user.id if message.from_user else None,
        username=message.from_user.username if message.from_user else None,
    )
    
    help_text = """
📚 <b>Comandos Disponíveis</b>

/start - Iniciar o bot
/help - Mostrar esta ajuda
/status - Ver status do sistema

━━━━━━━━━━━━━━━━━━━━━━

🤖 <b>Bot Integrador v1.0</b>
Integração entre plataformas de mensagens.
"""
    
    await message.answer(help_text.strip(), parse_mode="HTML")
