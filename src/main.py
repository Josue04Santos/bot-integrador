"""
Ponto de entrada principal da aplicação.
Orquestra: Bot DPL (aiogram) + UserBot (Telethon) + Worker (consumer da fila).
"""

import asyncio
import sys

import uvicorn

from src.bot import create_bot, create_dispatcher, on_shutdown, on_startup
from src.database.connection import db
from src.services import cache_service
from src.userbot import userbot
from src.userbot.scheduler import cache_refresh_loop
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
    async with db.session() as session:
        await cache_service.ensure_schema(session)

    # 2) Bot DPL
    bot = create_bot()
    dp = create_dispatcher()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # 3) UserBot Telethon
    ub_ok = await userbot.start(alert_bot=bot)
    if not ub_ok:
        logger.warning("UserBot NÃO conectou — consultas ficarão indisponíveis")
    else:
        logger.info("UserBot conectado com sucesso")

    # 4) Roda Bot DPL + Worker + Dashboard web em paralelo
    web = uvicorn.Server(uvicorn.Config(
        "src.api.main:app",
        host="0.0.0.0",
        port=8080,
        log_level="warning",
    ))

    try:
        logger.info("Iniciando Bot + Worker + Dashboard (porta 8080)...")
        await asyncio.gather(
            dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
            worker_loop(bot),
            cache_refresh_loop(),
            web.serve(),
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
