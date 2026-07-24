"""
Configuração e criação da aplicação do bot Telegram.
"""

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from src.bot.handlers import register_handlers
from src.bot.middlewares import setup_middlewares
from src.config import settings

logger = structlog.get_logger(__name__)

# Comandos visíveis pra todo mundo no menu "/" do Telegram
_COMANDOS_PUBLICOS = [
    BotCommand(command="start", description="Iniciar o bot"),
    BotCommand(command="help", description="Ajuda e instruções"),
    BotCommand(command="status", description="Status do bot e da fila"),
    BotCommand(command="whoami", description="Ver seu perfil e permissões"),
    BotCommand(command="kml", description="Baixar KML/CSV de um lote antigo"),
]

# Comandos extras, só pros super admins (settings.super_admin_ids)
_COMANDOS_ADMIN = _COMANDOS_PUBLICOS + [
    BotCommand(command="autorizar", description="Autorizar novo usuário"),
    BotCommand(command="desautorizar", description="Desativar um usuário"),
    BotCommand(command="usuarios", description="Listar usuários cadastrados"),
    BotCommand(command="promover", description="Promover usuário a admin"),
    BotCommand(command="naocadastrados", description="Listar códigos não cadastrados"),
    BotCommand(command="excluirnaocadastrado", description="Remover código da lista de não cadastrados"),
]


async def _configurar_comandos(bot: Bot) -> None:
    """Atualiza o menu '/' do Telegram com os comandos reais do bot."""
    await bot.set_my_commands(_COMANDOS_PUBLICOS, scope=BotCommandScopeDefault())
    for admin_id in settings.super_admin_ids:
        try:
            await bot.set_my_commands(
                _COMANDOS_ADMIN, scope=BotCommandScopeChat(chat_id=admin_id)
            )
        except Exception:
            logger.exception("Falha ao configurar comandos de admin", admin_id=admin_id)


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
    await _configurar_comandos(bot)
    logger.info("Menu de comandos do Telegram atualizado")


async def on_shutdown(bot: Bot) -> None:
    """
    Callback executado quando o bot é encerrado.
    
    Args:
        bot: Instância do bot.
    """
    logger.info("Bot encerrado")
    await bot.session.close()
