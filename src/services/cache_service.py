"""
Cache de consultas — 1 linha por código único na tabela code_cache.

Regras:
- Consulta nova   → INSERT
- Consulta repetida → UPDATE (upsert via on_conflict_do_update)
- TTL padrão: 7 dias. Stale = entrega do cache + refresh em background.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import CodeCache

CACHE_TTL_DAYS = 7


async def lookup(
    session: AsyncSession,
    code: str,
    query_type: str,
) -> Optional[CodeCache]:
    """Retorna o registro de cache para esse código, ou None se não existir."""
    stmt = (
        select(CodeCache)
        .where(CodeCache.code == code)
        .where(CodeCache.query_type == query_type)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def upsert(
    session: AsyncSession,
    code: str,
    query_type: str,
    raw_response: str,
    parsed_data: Optional[dict] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    alimentador: Optional[str] = None,
) -> CodeCache:
    """
    Insere ou atualiza o cache para esse código.
    Nunca cria linhas duplicadas — upsert por (code, query_type).
    """
    now = datetime.now(timezone.utc)

    # Tenta atualizar primeiro
    existing = await lookup(session, code, query_type)
    if existing:
        existing.raw_response = raw_response
        existing.parsed_data = parsed_data
        existing.latitude = latitude
        existing.longitude = longitude
        existing.alimentador = alimentador
        existing.last_fetched_at = now
        existing.fetch_count += 1
        await session.flush()
        return existing

    # Não existe → insere
    entry = CodeCache(
        code=code,
        query_type=query_type,
        raw_response=raw_response,
        parsed_data=parsed_data,
        latitude=latitude,
        longitude=longitude,
        alimentador=alimentador,
        first_fetched_at=now,
        last_fetched_at=now,
        fetch_count=1,
    )
    session.add(entry)
    await session.flush()
    return entry


def is_fresh(entry: CodeCache, ttl_days: int = CACHE_TTL_DAYS) -> bool:
    """True se o cache ainda está dentro do TTL."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
    last = entry.last_fetched_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return last >= cutoff


def age_label(entry: CodeCache) -> str:
    """Texto legível da idade do cache. Ex: '2h atrás', '3d atrás'."""
    last = entry.last_fetched_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - last
    if delta.days >= 1:
        return f"{delta.days}d atrás"
    hours = delta.seconds // 3600
    if hours >= 1:
        return f"{hours}h atrás"
    minutes = delta.seconds // 60
    return f"{minutes}min atrás"
