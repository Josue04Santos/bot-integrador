"""
Auto-refresh do cache — atualização automática em background.

Para não sobrecarregar o bot externo, cada código é classificado em um
dia fixo da semana (hash estável do código, não depende do processo).
O job diário só atualiza os códigos:
  1. já vencidos (TTL do cache_service), e
  2. cujo dia da semana designado é hoje.

Isso espalha ~1/7 do cache por dia, mantendo a cadência mínima entre
consultas reais ao bot externo (mesma usada pelo worker).
"""
import asyncio
import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from src.config import settings
from src.database.connection import db
from src.database.models import CodeCache
from src.services import cache_service
from src.userbot import userbot
from src.utils.logger import get_logger

logger = get_logger(__name__)

_MIN_INTERVAL_BETWEEN_REFRESHES = 8.0  # mesma cadência do worker (src/userbot/worker.py)


def _dia_do_codigo(code: str) -> int:
    """Dia da semana (0=segunda ... 6=domingo) fixo e estável para este código."""
    h = hashlib.md5(code.encode()).hexdigest()
    return int(h, 16) % 7


async def _codigos_stale_de_hoje() -> list[CodeCache]:
    """
    Candidatos ao auto-refresh de hoje: vencidos (TTL) E ainda em uso real
    (acessados dentro da janela de atividade). Isso limita o tamanho do job
    ao conjunto de códigos ativos, não ao histórico total — que só cresce.
    """
    cutoff_ttl = datetime.now(timezone.utc) - timedelta(days=cache_service.CACHE_TTL_DAYS)
    cutoff_atividade = datetime.now(timezone.utc) - timedelta(
        days=settings.cache_auto_refresh_activity_days
    )
    hoje = datetime.now(timezone.utc).weekday()
    async with db.session() as session:
        result = await session.execute(
            select(CodeCache)
            .where(CodeCache.last_fetched_at < cutoff_ttl)
            .where(CodeCache.last_accessed_at >= cutoff_atividade)
        )
        todos = result.scalars().all()
    return [c for c in todos if _dia_do_codigo(c.code) == hoje]


async def _refresh_um(entry: CodeCache) -> bool:
    if entry.query_type == "instalacao":
        resposta = await userbot.query_equipamento(entry.code)
    else:
        resposta = await userbot.query_poste(entry.code)
    if not resposta:
        return False
    async with db.session() as session:
        await cache_service.upsert(
            session,
            code=entry.code,
            query_type=entry.query_type,
            raw_response=resposta,
        )
    return True


async def _run_daily_refresh() -> None:
    candidatos = await _codigos_stale_de_hoje()
    if not candidatos:
        logger.info("Auto-refresh diário: nenhum código stale designado para hoje")
        return

    logger.info(f"Auto-refresh diário iniciado: {len(candidatos)} código(s)")
    ok = falhas = 0
    for entry in candidatos:
        if not userbot.is_connected:
            logger.warning("Auto-refresh interrompido — userbot desconectado")
            break
        try:
            sucesso = await _refresh_um(entry)
            ok += int(sucesso)
            falhas += int(not sucesso)
        except Exception:
            logger.exception(f"Falha no auto-refresh de {entry.code}")
            falhas += 1
        await asyncio.sleep(_MIN_INTERVAL_BETWEEN_REFRESHES)

    logger.info(f"Auto-refresh diário concluído: {ok} ok, {falhas} falha(s) de {len(candidatos)} total")


async def cache_refresh_loop() -> None:
    """Loop infinito: dispara o refresh diário sempre no horário configurado."""
    if not settings.cache_auto_refresh_enabled:
        logger.info("Auto-refresh de cache desabilitado (cache_auto_refresh_enabled=False)")
        return

    while True:
        agora = datetime.now()
        proxima = agora.replace(
            hour=settings.cache_auto_refresh_hour, minute=0, second=0, microsecond=0
        )
        if proxima <= agora:
            proxima += timedelta(days=1)
        espera = (proxima - agora).total_seconds()
        logger.info(f"Auto-refresh de cache: próxima execução em {espera / 3600:.1f}h ({proxima})")
        await asyncio.sleep(espera)
        try:
            await _run_daily_refresh()
        except Exception:
            logger.exception("Erro no ciclo de auto-refresh de cache")
