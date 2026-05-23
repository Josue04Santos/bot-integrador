"""
Configuração e criação da aplicação do bot Telegram.
"""

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from src.bot.handlers import register_handlers
from src.bot.middlewares import setup_middlewares
from src.config import settings

logger = structlog.get_logger(__name__)


def create_bot() -> Bot:
    """
    Cria e configura a instância do Bot.
    
    Returns:
        Bot configurado com token e propriedades padrão.
    """
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    logger.info("Bot criado com sucesso")
    return bot


def create_dispatcher() -> Dispatcher:
    """
    Cria e configura o Dispatcher com handlers e middlewares.
    
    Returns:
        Dispatcher configurado e pronto para uso.
    """
    dp = Dispatcher()
    
    # Registra middlewares
    setup_middlewares(dp)
    
    # Registra handlers (inclui admin)
    register_handlers(dp)
    logger.debug("Handlers registrados")
    
    logger.info("Dispatcher criado com sucesso")
    return dp


async def on_startup(bot: Bot) -> None:
    """
    Callback executado quando o bot inicia.
    
    Args:
        bot: Instância do bot.
    """
    bot_info = await bot.get_me()
    logger.info(
        "Bot iniciado",
        bot_id=bot_info.id,
        bot_username=bot_info.username,
        bot_name=bot_info.first_name,
    )


async def on_shutdown(bot: Bot) -> None:
    """
    Callback executado quando o bot é encerrado.
    
    Args:
        bot: Instância do bot.
    """
    logger.info("Bot encerrado")
    await bot.session.close()
