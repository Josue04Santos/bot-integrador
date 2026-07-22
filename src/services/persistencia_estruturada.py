"""
Persistência das tabelas estruturadas (`postes`, `equipamentos`, `componentes`).

Serviço único, chamado tanto pelo worker do bot DPL (`src/userbot/worker.py`)
quanto pelo cliente Telegram exclusivo da API (`src/userbot_consulta_api/`) —
qualquer consulta bem-sucedida, de qualquer um dos dois clients, passa por
aqui e vira dado estruturado consultável.

Não persiste nada quando o parser indica "não encontrado" ou "resposta
vazia" — quem chama trata isso como not-found (`salvar_*` retorna `None`).
"""
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models_estruturados import Componente, Equipamento, Poste
from src.parsing.equipamento import parse_equipamento
from src.parsing.poste import parse_poste


async def salvar_poste(
    session: AsyncSession,
    code: str,
    raw: str,
    origem_client: str,
) -> Optional[Poste]:
    """Parseia e faz upsert de um poste. Retorna None se não encontrado/inválido."""
    resultado = parse_poste(code, raw)
    if not resultado.ok:
        return None

    stmt = select(Poste).where(Poste.code == code)
    existente = (await session.execute(stmt)).scalar_one_or_none()

    campos = dict(
        latitude=resultado.latitude,
        longitude=resultado.longitude,
        alimentadores=resultado.alimentadores,
        cabos_mt=resultado.cabos_mt,
        cabos_bt=resultado.cabos_bt,
        estruturas_mt=resultado.estruturas_mt,
        estruturas_bt=resultado.estruturas_bt,
        raw_response=raw,
        origem_client=origem_client,
    )

    if existente:
        for campo, valor in campos.items():
            setattr(existente, campo, valor)
        await session.flush()
        return existente

    poste = Poste(code=code, **campos)
    session.add(poste)
    await session.flush()
    return poste


async def salvar_equipamento(
    session: AsyncSession,
    code: str,
    raw: str,
    origem_client: str,
) -> Optional[Equipamento]:
    """
    Parseia e faz upsert de um equipamento + substitui por completo seus
    componentes (delete + insert, mesma transação). Retorna None se não
    encontrado/inválido.
    """
    resultado = parse_equipamento(code, raw)
    if not resultado.ok:
        return None

    stmt = select(Equipamento).where(Equipamento.code == code)
    existente = (await session.execute(stmt)).scalar_one_or_none()

    campos = dict(
        instalacao=resultado.instalacao,
        tipo=resultado.tipo,
        poste_referencia=resultado.poste_referencia,
        potencia=resultado.potencia,
        tensao_primaria=resultado.tensao_primaria,
        tensao_secundaria=resultado.tensao_secundaria,
        fase=resultado.fase,
        clientes_total=resultado.clientes_total,
        situacao=resultado.situacao,
        perimetro=resultado.perimetro,
        alimentador=resultado.alimentador,
        latitude=resultado.latitude,
        longitude=resultado.longitude,
        raw_response=raw,
        origem_client=origem_client,
    )

    if existente:
        for campo, valor in campos.items():
            setattr(existente, campo, valor)
        equipamento = existente
        await session.flush()
        # Substitui componentes por completo — nunca acumula duplicata
        await session.execute(delete(Componente).where(Componente.equipamento_id == equipamento.id))
    else:
        equipamento = Equipamento(code=code, **campos)
        session.add(equipamento)
        await session.flush()

    for c in resultado.componentes:
        session.add(Componente(
            equipamento_id=equipamento.id,
            tipo=c.tipo,
            componente_code=c.componente_code,
            elo=c.elo,
            clientes=c.clientes,
            trafos=c.trafos,
            ordem=c.ordem,
        ))

    await session.flush()
    return equipamento


async def salvar(
    session: AsyncSession,
    code: str,
    query_type: str,
    raw: str,
    origem_client: str,
):
    """Despacha para salvar_poste/salvar_equipamento conforme `query_type`."""
    if query_type == "poste":
        return await salvar_poste(session, code, raw, origem_client)
    return await salvar_equipamento(session, code, raw, origem_client)
