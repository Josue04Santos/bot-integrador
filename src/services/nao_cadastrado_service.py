"""
Registro/histórico de códigos confirmados como "não cadastrado", com
TTL de 7 dias — dentro do prazo, evita reconsultar o bot terceiro à toa.
"""
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models_nao_cadastrado import CodigoNaoCadastrado


async def buscar(
    session: AsyncSession,
    code: str,
    query_type: str,
) -> CodigoNaoCadastrado | None:
    stmt = select(CodigoNaoCadastrado).where(
        CodigoNaoCadastrado.code == code,
        CodigoNaoCadastrado.query_type == query_type,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def buscar_recente(
    session: AsyncSession,
    code: str,
    query_type: str,
) -> CodigoNaoCadastrado | None:
    """Retorna a entrada só se ainda estiver dentro do TTL (7 dias)."""
    entry = await buscar(session, code, query_type)
    return entry if entry and entry.is_fresh else None


async def registrar(
    session: AsyncSession,
    code: str,
    query_type: str,
    raw_response: str,
) -> None:
    """Upsert — registra (ou atualiza) a confirmação de que o código não existe."""
    entry = await buscar(session, code, query_type)
    now = datetime.now(timezone.utc)

    if entry:
        entry.raw_response = raw_response
        entry.ultima_vez = now
        entry.vezes_confirmado += 1
    else:
        session.add(CodigoNaoCadastrado(
            code=code, query_type=query_type, raw_response=raw_response,
            primeira_vez=now, ultima_vez=now, vezes_confirmado=1,
        ))


async def listar(session: AsyncSession, limit: int = 20) -> list[CodigoNaoCadastrado]:
    stmt = (
        select(CodigoNaoCadastrado)
        .order_by(CodigoNaoCadastrado.ultima_vez.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def remover(session: AsyncSession, code: str, query_type: str) -> bool:
    result = await session.execute(
        delete(CodigoNaoCadastrado).where(
            CodigoNaoCadastrado.code == code,
            CodigoNaoCadastrado.query_type == query_type,
        )
    )
    return bool(result.rowcount)
