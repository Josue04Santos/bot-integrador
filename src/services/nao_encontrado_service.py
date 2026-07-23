"""
Códigos confirmados como "não cadastrado" — evita reconsultar ao vivo um
código que já sabemos que não existe, dentro do TTL (30 dias).
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models_nao_encontrado import CodigoNaoEncontrado


async def esta_confirmado_nao_encontrado(
    session: AsyncSession,
    code: str,
    query_type: str,
) -> bool:
    """True se já confirmamos ao vivo, dentro do TTL, que esse código não existe."""
    stmt = select(CodigoNaoEncontrado).where(
        CodigoNaoEncontrado.code == code,
        CodigoNaoEncontrado.query_type == query_type,
    )
    entry = (await session.execute(stmt)).scalar_one_or_none()
    return entry is not None and entry.is_fresh


async def marcar_nao_encontrado(
    session: AsyncSession,
    code: str,
    query_type: str,
) -> None:
    """Upsert — registra (ou renova) a confirmação de que o código não existe."""
    stmt = select(CodigoNaoEncontrado).where(
        CodigoNaoEncontrado.code == code,
        CodigoNaoEncontrado.query_type == query_type,
    )
    entry = (await session.execute(stmt)).scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if entry:
        entry.checked_at = now
    else:
        session.add(CodigoNaoEncontrado(code=code, query_type=query_type, checked_at=now))
