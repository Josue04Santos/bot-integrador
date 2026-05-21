"""
Ponto de entrada principal da aplicação.
"""

import asyncio
import sys

from src.bot import create_bot, create_dispatcher, on_shutdown, on_startup
from src.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


async def main() -> None:
    """
    Função principal que inicializa e executa o bot.
    """
    # Configura logging
    setup_logging()
    
    logger.info("=" * 50)
    logger.info("Iniciando Bot Integrador...")
    logger.info("=" * 50)
    
    # Cria instâncias
    bot = create_bot()
    dp = create_dispatcher()
    
    # Registra callbacks de ciclo de vida
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    try:
        # Inicia polling
        logger.info("Iniciando polling...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    except Exception as e:
        logger.critical(
            "Erro fatal na execução do bot",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise
    finally:
        logger.info("Aplicação finalizada")


def run() -> None:
    """
    Wrapper para execução do asyncio.
    """
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot interrompido pelo usuário (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Erro não tratado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run()
