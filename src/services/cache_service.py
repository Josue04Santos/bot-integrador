"""
Cache de consultas — 1 linha por código único na tabela code_cache.

Regras:
- Consulta nova   → INSERT
- Consulta repetida → UPDATE (upsert via on_conflict_do_update)
- TTL padrão: 7 dias. Stale = entrega do cache + refresh em background.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import CodeCache

CACHE_TTL_DAYS = 7

_DDL_ADD_LAST_ACCESSED_AT = sa.text(
    "ALTER TABLE code_cache "
    "ADD COLUMN IF NOT EXISTS last_accessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
)


async def ensure_schema(session: AsyncSession) -> None:
    """Migração idempotente — garante colunas novas em bancos já existentes."""
    await session.execute(_DDL_ADD_LAST_ACCESSED_AT)
    await session.commit()

# Marcadores que confirmam que a resposta é um dado real de poste/equipamento
_MARCADORES_VALIDOS = (
    "poste:",
    "instalação:",
    "instalacao:",
    "alimentador",
    "localização",
    "localizacao",
)

# Qualquer um desses invalida a resposta — não salva no cache
_MARCADORES_INVALIDOS = (
    "informe o número",
    "informe o numero",
    "comando não reconhecido",
    "comando nao reconhecido",
    "não cadastrado",
    "nao cadastrado",
    "não encontrado",
    "nao encontrado",
    "favor refazer",
    "código inválido",
    "codigo invalido",
)


def is_valid_response(raw_response: str) -> bool:
    """
    Retorna True apenas se a resposta contém dados reais de poste/equipamento.
    Impede que prompts, erros ou respostas misturadas entrem no cache.
    """
    if not raw_response or len(raw_response) < 50:
        return False
    lower = raw_response.lower()
    if any(inv in lower for inv in _MARCADORES_INVALIDOS):
        return False
    if not any(val in lower for val in _MARCADORES_VALIDOS):
        return False
    return True


async def lookup(
    session: AsyncSession,
    code: str,
    query_type: str,
) -> Optional[CodeCache]:
    """
    Retorna o registro de cache para esse código, ou None se não existir.
    Atualiza last_accessed_at — usado pelo auto-refresh para saber quais
    códigos ainda estão em uso real (ver src/userbot/scheduler.py).
    """
    stmt = (
        select(CodeCache)
        .where(CodeCache.code == code)
        .where(CodeCache.query_type == query_type)
    )
    result = await session.execute(stmt)
    entry = result.scalar_one_or_none()
    if entry:
        entry.last_accessed_at = datetime.now(timezone.utc)
        await session.flush()
    return entry


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
    if not is_valid_response(raw_response):
        from src.utils.logger import get_logger
        get_logger(__name__).warning(
            f"Cache REJEITADO — resposta inválida para {code}: {repr(raw_response[:80])}"
        )
        return None

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
