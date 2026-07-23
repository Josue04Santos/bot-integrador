"""
Registro/histórico de códigos confirmados como "não cadastrado".

Só registra — não pula consulta ao vivo (isso sempre acontece normalmente).
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models_nao_cadastrado import CodigoNaoCadastrado


async def registrar(
    session: AsyncSession,
    code: str,
    query_type: str,
    raw_response: str,
) -> None:
    """Upsert — registra (ou atualiza) a confirmação de que o código não existe."""
    stmt = select(CodigoNaoCadastrado).where(
        CodigoNaoCadastrado.code == code,
        CodigoNaoCadastrado.query_type == query_type,
    )
    entry = (await session.execute(stmt)).scalar_one_or_none()
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
