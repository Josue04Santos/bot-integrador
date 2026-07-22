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
from src.parsing.deteccao import is_not_found as _is_not_found
from src.services import cache_service, persistencia_estruturada
from src.userbot import userbot
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Controle de cadência — garante intervalo mínimo entre consultas reais ao bot externo.
# Necessário porque cache hits são instantâneos e a fila avança rápido demais,
# deixando o bot externo em estado inconsistente.
_last_real_query_time: float = 0.0
_MIN_INTERVAL_BETWEEN_REAL_QUERIES = 8.0  # segundos


async def _wait_for_bot_ready() -> None:
    """Aguarda o intervalo mínimo desde a última consulta real ao bot externo."""
    global _last_real_query_time
    elapsed = time.monotonic() - _last_real_query_time
    if elapsed < _MIN_INTERVAL_BETWEEN_REAL_QUERIES:
        wait = _MIN_INTERVAL_BETWEEN_REAL_QUERIES - elapsed
        logger.info(f"Cadência: aguardando {wait:.1f}s antes de chamar bot externo")
        await asyncio.sleep(wait)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _process_one(item: QueueItem, bot: Bot) -> None:
    """Processa uma única consulta com verificação de cache."""

    # ── Verifica cache ──────────────────────────────────────────────────────
    async with db.session() as session:
        cached = await cache_service.lookup(session, item.code, item.query_type)

    if cached is not None:
        # Dupla verificação: dado inválido no cache (legado ou contaminação)
        if not cache_service.is_valid_response(cached.raw_response or "") or _is_not_found(cached.raw_response or ""):
            async with db.session() as session:
                query = await session.get(NetworkQuery, item.query_id)
                if query:
                    query.status = "error"
                    query.error_message = "não cadastrado"
                    query.raw_response = cached.raw_response
            await _update_batch(item.batch_id, error=True)
            await _update_progress_message(bot, item.batch_id)
            await _check_batch_complete(bot, item.batch_id)
            return

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
        else:
            logger.info("Cache stale — refresh em background", code=item.code, age=age)
            asyncio.create_task(_background_refresh(item.code, item.query_type))

        await _update_progress_message(bot, item.batch_id)
        await _check_batch_complete(bot, item.batch_id)
        return

    # ── Cache miss: consulta o bot externo ──────────────────────────────────
    # Garante cadência mínima para não sobrecarregar o bot externo
    await _wait_for_bot_ready()

    async with db.session() as session:
        query = await session.get(NetworkQuery, item.query_id)
        if not query:
            logger.error("Query não encontrada", query_id=item.query_id)
            return
        query.status = "sent"
        query.sent_at = _utcnow()

    started = time.perf_counter()
    _last_real_query_time = time.monotonic()
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

    not_found = response is not None and _is_not_found(response)

    async with db.session() as session:
        query = await session.get(NetworkQuery, item.query_id)
        if response and not not_found:
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

            # Persiste dado estruturado (postes/equipamentos/componentes)
            await persistencia_estruturada.salvar(
                session,
                code=item.code,
                query_type=item.query_type,
                raw=response,
                origem_client="userbot",
            )
        elif not_found:
            # Resposta veio, mas o código não existe no sistema externo
            query.status = "error"
            query.error_message = "não cadastrado"
            query.raw_response = response  # guarda para auditoria
        elif error_msg:
            query.status = "error"
            query.error_message = error_msg
        else:
            query.status = "timeout"

    await _update_batch(
        item.batch_id,
        success=bool(response and not not_found),
        error=bool(error_msg or not_found),
    )
    await _update_progress_message(bot, item.batch_id)
    await _check_batch_complete(bot, item.batch_id)


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
                await persistencia_estruturada.salvar(
                    session,
                    code=code,
                    query_type=query_type,
                    raw=response,
                    origem_client="userbot",
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


async def _check_batch_complete(bot: Bot, batch_id: str) -> None:
    """Verifica se o batch terminou e finaliza a mensagem de progresso."""
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
        await _update_progress_message(bot, batch_id, force=True)
        logger.info("Batch finalizado", batch_id=batch_id[:8])


# Throttle de edições — evita rate limit do Telegram quando muitos cache-hits
# processam quase instantaneamente. A edição final (conclusão) sempre força.
_last_progress_edit: dict[str, float] = {}
_MIN_INTERVAL_BETWEEN_EDITS = 2.0  # segundos


def _format_duration(batch: QueryBatch) -> str:
    inicio = batch.started_at or batch.created_at
    fim = batch.finished_at or _utcnow()
    delta = (fim - inicio).total_seconds()
    return f"{delta:.1f}s" if delta < 60 else f"{delta / 60:.1f}min"


def _format_progress_text(batch: QueryBatch) -> tuple[str, bool]:
    """Retorna (texto, tem_sucesso) — tem_sucesso decide se anexa o botão de download."""
    if batch.status == "completed":
        ok, total = batch.success_count, batch.total_codes
        if ok == total:
            icon, status_text = "🎉", "Lote concluído com sucesso!"
        elif ok > 0:
            icon, status_text = "✅", "Lote concluído (com falhas)"
        else:
            icon, status_text = "⚠️", "Lote concluído sem sucesso"
        rodape = (
            "\n<i>Clique abaixo para baixar KML (Google Earth) + CSV.</i>" if ok > 0
            else "\n<i>Nenhum resultado disponível para exportar.</i>"
        )
        tem_sucesso = ok > 0
    else:
        icon, status_text = "🎉", "Lote em execução:"
        rodape = ""
        tem_sucesso = False

    text = (
        f"{icon} <b>{status_text}</b>\n\n"
        f"🆔 Lote: <code>#{batch.id[:8]}</code>\n"
        f"📊 Total: <b>{batch.total_codes}</b>\n"
        f"✅ OK: <b>{batch.success_count}</b>\n"
        f"❌ Erros: <b>{batch.failure_count}</b>\n"
        f"⏱️ Timeouts: <b>{batch.timeout_count}</b>\n"
        f"⏱️ Duração: <b>{_format_duration(batch)}</b>\n"
        f"{rodape}"
    )
    return text, tem_sucesso


async def _update_progress_message(bot: Bot, batch_id: str, force: bool = False) -> None:
    """
    Edita a mensagem única de progresso do lote — em vez de mandar 1 mensagem
    por resultado individual. `force=True` ignora o throttle (usado na
    conclusão, pra garantir que os números finais sempre apareçam).
    """
    if not force:
        last = _last_progress_edit.get(batch_id, 0.0)
        if time.monotonic() - last < _MIN_INTERVAL_BETWEEN_EDITS:
            return

    async with db.session() as session:
        batch = await session.get(QueryBatch, batch_id)
        if not batch or not batch.progress_chat_id or not batch.progress_message_id:
            return
        text, tem_sucesso = _format_progress_text(batch)
        chat_id = batch.progress_chat_id
        message_id = batch.progress_message_id

    from src.bot.keyboards.export import kml_download_kb

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=kml_download_kb(batch_id) if tem_sucesso else None,
        )
        _last_progress_edit[batch_id] = time.monotonic()
    except Exception as e:
        if "message is not modified" in str(e).lower():
            _last_progress_edit[batch_id] = time.monotonic()
            return
        logger.exception("Falha ao editar mensagem de progresso", batch_id=batch_id[:8])


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
