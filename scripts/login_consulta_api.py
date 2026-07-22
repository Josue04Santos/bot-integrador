"""
Login inicial do Telethon para a conta EXCLUSIVA de consultas via API.

Rode manualmente, num terminal interativo (vai pedir o código de
verificação enviado por Telegram e, se houver, a senha 2FA):

    python -m scripts.login_consulta_api

A sessão fica salva no Postgres (`telethon_sessions`, linha
"userbot_consulta_api") — só precisa rodar isso uma vez.
"""
import asyncio

from src.database.connection import db
from src.userbot_consulta_api import userbot_consulta_api


async def main() -> None:
    await db.initialize()
    ok = await userbot_consulta_api.start()
    if ok:
        print("✅ Login concluído e sessão salva no Postgres.")
    else:
        print("❌ Falha no login — confira CONSULTA_API_TELEGRAM_API_ID/HASH/PHONE no .env")
    await userbot_consulta_api.stop()
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
