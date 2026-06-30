"""
Worker que consome a fila e dispara consultas via UserBot.

Fluxo com cache (3 cenários):
  1. Código no cache e fresco (< 7d)  → entrega imediata, sem chamar bot externo
  2. Código no cache mas stale (≥ 7d) → entrega do cache + atualiza em background
  3. Código não está no cache         → consulta bot externo, faz upsert, entrega

A tabela code_cache tem 1 linha por código — nunca cria duplicatas.
"""

import asyncio
import time
from datetime import datetime, timezone

from aiogram import Bot

from src.database.connection import db
from src.database.models import NetworkQuery, QueryBatch
from src.dispatcher import query_queue, QueueItem
from src.services import cache_service
from src.userbot import userbot
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _process_one(item: QueueItem, bot: Bot) -> None:
    """Processa uma única consulta com verificação de cache."""

    # ── Verifica cache ──────────────────────────────────────────────────────
    async with db.session() as session:
        cached = await cache_service.lookup(session, item.code, item.query_type)

    if cached is not None:
        fresh = cache_service.is_fresh(cached)
        age = cache_service.age_label(cached)

        # Preenche a NetworkQuery do batch com dados do cache
        async with db.session() as session:
            query = await session.get(NetworkQuery, item.query_id)
            if query:
                query.status = "received"
                query.raw_response = cached.raw_response
                query.parsed_data = cached.parsed_data
                query.latitude = cached.latitude
                query.longitude = cached.longitude
                query.alimentador = cached.alimentador
                query.received_at = _utcnow()
                query.response_ms = 0

        await _update_batch(item.batch_id, success=True)

        if fresh:
            logger.info("Cache hit (fresco)", code=item.code, age=age)
            cache_info = f"📦 cache ({age})"
        else:
            logger.info("Cache stale — refresh em background", code=item.code, age=age)
            cache_info = f"📦 cache desatualizado ({age}) — atualizando…"
            asyncio.create_task(_background_refresh(item.code, item.query_type))

        await _notify_user(bot, item, cached.raw_response, error=None, cache_info=cache_info)
        await _check_batch_complete(bot, item.batch_id, item.chat_id)
        return

    # ── Cache miss: consulta o bot externo ──────────────────────────────────
    async with db.session() as session:
        query = await session.get(NetworkQuery, item.query_id)
        if not query:
            logger.error("Query não encontrada", query_id=item.query_id)
            return
        query.status = "sent"
        query.sent_at = _utcnow()

    started = time.perf_counter()
    try:
        if item.query_type == "instalacao":
            response = await userbot.query_equipamento(item.code)
        else:
            response = await userbot.query_poste(item.code)
    except Exception as e:
        logger.exception("Erro ao consultar userbot", code=item.code)
        response = None
        error_msg = f"{type(e).__name__}: {e}"
    else:
        error_msg = None

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    async with db.session() as session:
        query = await session.get(NetworkQuery, item.query_id)
        if response:
            query.status = "received"
            query.raw_response = response
            query.received_at = _utcnow()
            query.response_ms = elapsed_ms

            # Upsert no cache — 1 linha por código, sem duplicatas
            await cache_service.upsert(
                session,
                code=item.code,
                query_type=item.query_type,
                raw_response=response,
                parsed_data=query.parsed_data,
                latitude=query.latitude,
                longitude=query.longitude,
                alimentador=query.alimentador,
            )
        elif error_msg:
            query.status = "error"
            query.error_message = error_msg
        else:
            query.status = "timeout"

    await _update_batch(item.batch_id, success=bool(response), error=bool(error_msg))
    await _notify_user(bot, item, response, error_msg, cache_info=None)
    await _check_batch_complete(bot, item.batch_id, item.chat_id)


async def _background_refresh(code: str, query_type: str) -> None:
    """Atualiza silenciosamente um cache stale — sem notificar o usuário."""
    logger.info("Background refresh iniciado", code=code)
    try:
        if query_type == "instalacao":
            response = await userbot.query_equipamento(code)
        else:
            response = await userbot.query_poste(code)

        if response:
            async with db.session() as session:
                await cache_service.upsert(
                    session,
                    code=code,
                    query_type=query_type,
                    raw_response=response,
                )
            logger.info("Background refresh concluído", code=code)
        else:
            logger.warning("Background refresh sem resposta", code=code)
    except Exception:
        logger.exception("Falha no background refresh", code=code)


async def _update_batch(
    batch_id: str,
    success: bool = False,
    error: bool = False,
) -> None:
    """Atualiza contadores do batch."""
    async with db.session() as session:
        batch = await session.get(QueryBatch, batch_id)
        if not batch:
            return
        if success:
            batch.success_count += 1
        elif error:
            batch.failure_count += 1
        else:
            batch.timeout_count += 1
        if not batch.started_at:
            batch.started_at = _utcnow()
        batch.status = "running"


async def _check_batch_complete(bot: Bot, batch_id: str, chat_id: int) -> None:
    """Verifica se o batch terminou e dispara notificação de conclusão."""
    batch_just_completed = False
    async with db.session() as session:
        batch = await session.get(QueryBatch, batch_id)
        if not batch:
            return
        done = batch.success_count + batch.failure_count + batch.timeout_count
        if done >= batch.total_codes and batch.status != "completed":
            batch.status = "completed"
            batch.finished_at = _utcnow()
            batch_just_completed = True

    if batch_just_completed:
        await _notify_batch_complete(bot, batch_id, chat_id)


async def _notify_batch_complete(bot: Bot, batch_id: str, chat_id: int) -> None:
    """Envia resumo de conclusão do lote + botão de download."""
    from src.bot.keyboards.export import kml_download_kb

    async with db.session() as session:
        batch = await session.get(QueryBatch, batch_id)
        if not batch:
            return
        total = batch.total_codes
        ok = batch.success_count
        err = batch.failure_count
        timeout = batch.timeout_count
        duration_str = ""
        if batch.started_at and batch.finished_at:
            delta = (batch.finished_at - batch.started_at).total_seconds()
            duration_str = (
                f"⏱ Duração: <b>{delta:.1f}s</b>\n"
                if delta < 60
                else f"⏱ Duração: <b>{delta / 60:.1f}min</b>\n"
            )

    if ok == total:
        icon, status_text = "🎉", "Lote concluído com sucesso!"
    elif ok > 0:
        icon, status_text = "✅", "Lote concluído (com falhas)"
    else:
        icon, status_text = "⚠️", "Lote concluído sem sucesso"

    tem_sucesso = ok > 0

    text = (
        f"{icon} <b>{status_text}</b>\n\n"
        f"🆔 Lote: <code>#{batch_id[:8]}</code>\n"
        f"📊 Total: <b>{total}</b>\n"
        f"✅ OK: <b>{ok}</b>\n"
        f"❌ Erros: <b>{err}</b>\n"
        f"⏱ Timeouts: <b>{timeout}</b>\n"
        f"{duration_str}"
        + (f"\n<i>Clique abaixo para baixar KML (Google Earth) + CSV.</i>" if tem_sucesso else
           f"\n<i>Nenhum resultado disponível para exportar.</i>")
    )

    try:
        await bot.send_message(
            chat_id, text,
            reply_markup=kml_download_kb(batch_id) if tem_sucesso else None,
        )
        logger.info("Batch finalizado", batch_id=batch_id[:8], ok=ok, total=total)
    except Exception:
        logger.exception("Falha ao notificar conclusão do batch", batch_id=batch_id[:8])


async def _notify_user(
    bot: Bot,
    item: QueueItem,
    response: str | None,
    error: str | None,
    cache_info: str | None,
) -> None:
    """Envia o resultado individual ao usuário."""
    tipo_label = "🏗️ POSTE" if item.query_type == "poste" else "⚡ EQUIPAMENTO"
    header = f"{tipo_label} • <code>{item.code}</code>"
    cache_line = f"\n<i>{cache_info}</i>" if cache_info else ""

    if response:
        body = response if len(response) < 3800 else response[:3800] + "\n\n[...truncado]"
        text = f"✅ <b>Resultado</b>{cache_line}\n{header}\n\n<pre>{body}</pre>"
    elif error:
        text = f"❌ <b>Erro</b>\n{header}\n\n<code>{error}</code>"
    else:
        text = f"⏱ <b>Timeout</b>\n{header}\n\nSem resposta do bot remoto."

    try:
        await bot.send_message(item.chat_id, text)
    except Exception:
        logger.exception("Falha ao notificar user", chat_id=item.chat_id)


async def worker_loop(bot: Bot) -> None:
    """Loop infinito do worker."""
    logger.info("Worker do UserBot iniciado")
    while True:
        item = await query_queue.get()
        try:
            await _process_one(item, bot)
        except Exception:
            logger.exception("Erro inesperado no worker", item=item)
        finally:
            query_queue.task_done()
