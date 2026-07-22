"""
Script de teste ISOLADO — sobe o bot de chat (aiogram) + worker + cache
usando um bot token diferente (ex: @Fluxon8nSul_bot), SEM iniciar o
userbot Telethon (evita colidir com a sessão que a produção já está usando).

Só funciona de verdade pra códigos que já estão em cache — consultas novas
(cache-miss) vão falhar silenciosamente (userbot não conectado), o que é
esperado neste modo de teste.

Uso:
    TELEGRAM_BOT_TOKEN="<token do bot de teste>" python -m scripts.test_bot_mensagens
"""
import asyncio

import uvicorn

from src.bot import create_bot, create_dispatcher, on_shutdown, on_startup
from src.database.connection import db
from src.services import cache_service
from src.userbot.worker import worker_loop
from src.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


async def main() -> None:
    setup_logging()
    logger.info("=== TESTE ISOLADO — sem userbot Telethon (só mensagens/cache) ===")

    await db.initialize()
    async with db.session() as session:
        await cache_service.ensure_schema(session)

    bot = create_bot()
    dp = create_dispatcher()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    web = uvicorn.Server(uvicorn.Config(
        "src.api.main:app",
        host="127.0.0.1",
        port=8098,  # porta diferente da produção (8080), evita conflito
        log_level="warning",
    ))

    try:
        await asyncio.gather(
            dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
            worker_loop(bot),
            web.serve(),
        )
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
