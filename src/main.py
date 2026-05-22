"""
Ponto de entrada principal da aplicação.
Orquestra: Bot DPL (aiogram) + UserBot (Telethon) + Worker (consumer da fila).
"""

import asyncio
import sys

from src.bot import create_bot, create_dispatcher, on_shutdown, on_startup
from src.database.connection import db
from src.userbot import userbot
from src.userbot.worker import worker_loop
from src.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


async def main() -> None:
    setup_logging()

    logger.info("=" * 50)
    logger.info("Iniciando Bot Integrador...")
    logger.info("=" * 50)

    # 1) Banco
    await db.initialize()

    # 2) Bot DPL
    bot = create_bot()
    dp = create_dispatcher()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # 3) UserBot Telethon
    ub_ok = await userbot.start()
    if not ub_ok:
        logger.warning("UserBot NÃO conectou — consultas ficarão indisponíveis")
    else:
        logger.info("UserBot conectado com sucesso")

    # 4) Roda Bot DPL + Worker em paralelo
    try:
        logger.info("Iniciando polling do Bot + Worker do UserBot...")
        await asyncio.gather(
            dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
            worker_loop(bot),
        )
    except Exception as e:
        logger.critical(
            "Erro fatal na execução",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise
    finally:
        await userbot.stop()
        await db.close()
        logger.info("Aplicação finalizada")


def run() -> None:
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
