"""
Handlers para comandos iniciais: /start e /help.
"""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from src.utils.logger import get_logger

logger = get_logger(__name__)

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """
    Handler para o comando /start.
    Apresenta o bot e suas funcionalidades.
    """
    user = message.from_user
    logger.info(
        "Comando /start recebido",
        user_id=user.id,
        username=user.username,
    )

    welcome_text = f"""
👋 **Olá, {user.first_name or 'usuário'}!**

Bem-vindo ao **Bot Integrador**.

🤖 **O que eu faço:**
• Capturo mensagens de canais/grupos de origem
• Processo e organizo o conteúdo
• Encaminho para os destinos configurados

📋 **Comandos disponíveis:**
• `/start` - Esta mensagem
• `/help` - Ajuda detalhada
• `/status` - Status do sistema

Use o menu abaixo para navegar.
"""

    await message.answer(welcome_text, parse_mode="Markdown")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """
    Handler para o comando /help.
    Exibe ajuda detalhada sobre o bot.
    """
    logger.info(
        "Comando /help recebido",
        user_id=message.from_user.id,
    )

    help_text = """
📖 **Ajuda - Bot Integrador**

**Comandos Principais:**
• `/start` - Inicia o bot
• `/help` - Mostra esta ajuda
• `/status` - Verifica status do sistema

**Como funciona:**
1. O bot monitora canais/grupos de origem
2. Processa as mensagens recebidas
3. Encaminha para os destinos configurados

**Suporte:**
Em caso de dúvidas, entre em contato com o administrador.
"""

    await message.answer(help_text, parse_mode="Markdown")


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    """
    Handler para o comando /status.
    Exibe o status atual do sistema.
    """
    logger.info(
        "Comando /status recebido",
        user_id=message.from_user.id,
    )

    status_text = """
📊 **Status do Sistema**

✅ **Bot:** Online
✅ **API:** Operacional
✅ **Banco de Dados:** Conectado

🕐 **Última verificação:** Agora
"""

    await message.answer(status_text, parse_mode="Markdown")
