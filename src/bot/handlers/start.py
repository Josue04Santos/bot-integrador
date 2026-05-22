"""
Handlers /start e /status.
(O /help está no módulo dedicado src/bot/handlers/help.py)
"""

import time
from datetime import datetime, timezone

from aiogram import Bot, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from sqlalchemy import text

from src.bot.keyboards.main_menu import main_menu_kb
from src.database.connection import db
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="start")

_BOOT_TIME = time.time()


@router.message(CommandStart())
async def cmd_start(message: Message, auth_user_full_name: str | None) -> None:
    """Mensagem de boas-vindas + botões de consulta."""
    user = message.from_user
    logger.info("/start", user_id=user.id, username=user.username)

    nome = auth_user_full_name or user.first_name or "usuário"

    welcome_text = (
        f"👋 <b>Olá, {nome}!</b>\n\n"
        "Bem-vindo ao <b>Bot Integrador EQTL</b>.\n\n"
        "🔍 <b>O que você quer consultar?</b>\n"
        "Escolha abaixo o tipo de consulta:\n\n"
        "🏗️ <b>POSTE</b> — consulta dados de um poste pelo código\n"
        "⚡ <b>EQUIPAMENTO</b> — consulta uma instalação/equipamento\n\n"
        "<i>💡 Você poderá enviar 1 código, vários (separados por vírgula/espaço) "
        "ou um arquivo .txt com a lista.</i>"
    )

    await message.answer(welcome_text, reply_markup=main_menu_kb())


@router.message(Command("status"))
async def cmd_status(message: Message, bot: Bot) -> None:
    """Status REAL do sistema."""
    logger.info("/status", user_id=message.from_user.id)

    # --- Bot (Telegram API) ---
    t0 = time.perf_counter()
    try:
        me = await bot.get_me()
        bot_ms = round((time.perf_counter() - t0) * 1000, 1)
        bot_line = f"✅ <b>Bot:</b> online (@{me.username}) — {bot_ms}ms"
    except Exception as e:
        bot_line = f"❌ <b>Bot:</b> erro — <code>{type(e).__name__}</code>"

    # --- Postgres ---
    t0 = time.perf_counter()
    try:
        async with db.session() as session:
            await session.execute(text("SELECT 1"))
        db_ms = round((time.perf_counter() - t0) * 1000, 1)
        db_line = f"✅ <b>Banco de dados:</b> conectado — {db_ms}ms"
    except Exception as e:
        db_line = f"❌ <b>Banco de dados:</b> erro — <code>{type(e).__name__}</code>"

    # --- UserBot (Telethon) ---
    try:
        from src.userbot import userbot
        if userbot.is_connected:
            ub_line = "✅ <b>UserBot:</b> conectado"
        else:
            ub_line = "⚠️ <b>UserBot:</b> desconectado (consultas indisponíveis)"
    except Exception:
        ub_line = "⚠️ <b>UserBot:</b> não inicializado"

    # --- Fila ---
    try:
        from src.dispatcher import query_queue
        qsize = query_queue.size()
        queue_line = f"📦 <b>Fila:</b> {qsize} consulta(s) pendente(s)"
    except Exception:
        queue_line = "📦 <b>Fila:</b> indisponível"

    # --- Uptime ---
    up_seconds = int(time.time() - _BOOT_TIME)
    h, rem = divmod(up_seconds, 3600)
    m, s = divmod(rem, 60)
    uptime = f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    status_text = (
        "📊 <b>Status do Sistema</b>\n\n"
        f"{bot_line}\n"
        f"{db_line}\n"
        f"{ub_line}\n"
        f"{queue_line}\n\n"
        f"⏱ <b>Uptime:</b> {uptime}\n"
        f"🕐 <b>Verificado em:</b> {now_utc}"
    )

    await message.answer(status_text)
