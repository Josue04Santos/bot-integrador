"""
Endpoint de consulta para o Naeg (DPL) — cálculo de CHI.

Cache-first: busca nas tabelas estruturadas (postes / equipamentos+componentes).
Se não encontrar, consulta ao vivo via `userbot_consulta_api` (client Telegram
exclusivo, conta separada do bot DPL) e persiste antes de responder.

Se `userbot_consulta_api` não estiver configurado (sem credenciais ainda),
o endpoint funciona só em modo cache — cache-miss vira 404 direto, sem
tentar consulta ao vivo. Ver API_CHI.md para o contrato completo.
"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from src.api.deps import verify_api_key
from src.config import settings
from src.database.connection import db
from src.database.models_estruturados import Equipamento, Poste
from src.services import persistencia_estruturada
from src.userbot_consulta_api import userbot_consulta_api
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/chi", tags=["chi"])


class PosteOut(BaseModel):
    code: str
    latitude: float | None
    longitude: float | None
    alimentadores: list[str] | None
    cabos_mt: list[str] | None
    cabos_bt: list[str] | None

    model_config = {"from_attributes": True}


class EquipamentoOut(BaseModel):
    code: str
    tipo: str | None
    poste_referencia: str | None
    potencia: str | None
    tensao_primaria: str | None
    fase: str | None
    clientes_total: int | None
    situacao: str | None
    perimetro: str | None
    alimentador: str | None

    model_config = {"from_attributes": True}


class ChiResponse(BaseModel):
    success: bool
    codigo: str
    tipo: str
    origem: str  # "cache" | "bot_externo"
    poste: PosteOut | None = None
    equipamento: EquipamentoOut | None = None


@router.get("/{codigo}", response_model=ChiResponse)
async def consultar_chi(
    codigo: str,
    tipo: str = Query(..., pattern="^(poste|equipamento)$"),
    api_key: str = Depends(verify_api_key),
) -> ChiResponse:
    if tipo == "poste":
        return await _consultar_poste(codigo)
    return await _consultar_equipamento(codigo)


async def _consultar_poste(codigo: str) -> ChiResponse:
    async with db.session() as session:
        poste = (
            await session.execute(select(Poste).where(Poste.code == codigo))
        ).scalar_one_or_none()

    if poste:
        return ChiResponse(
            success=True, codigo=codigo, tipo="poste", origem="cache",
            poste=PosteOut.model_validate(poste),
        )

    raw = await _consultar_ao_vivo(codigo, tipo="poste")

    async with db.session() as session:
        poste = await persistencia_estruturada.salvar_poste(
            session, codigo, raw, origem_client="userbot_consulta_api"
        )

    if not poste:
        raise HTTPException(status_code=404, detail="Código não cadastrado no sistema")

    return ChiResponse(
        success=True, codigo=codigo, tipo="poste", origem="bot_externo",
        poste=PosteOut.model_validate(poste),
    )


async def _consultar_equipamento(codigo: str) -> ChiResponse:
    async with db.session() as session:
        stmt = select(Equipamento).where(Equipamento.code == codigo)
        equipamento = (await session.execute(stmt)).scalar_one_or_none()

    if equipamento:
        return ChiResponse(
            success=True, codigo=codigo, tipo="equipamento", origem="cache",
            equipamento=EquipamentoOut.model_validate(equipamento),
        )

    raw = await _consultar_ao_vivo(codigo, tipo="equipamento")

    async with db.session() as session:
        equipamento = await persistencia_estruturada.salvar_equipamento(
            session, codigo, raw, origem_client="userbot_consulta_api"
        )

    if not equipamento:
        raise HTTPException(status_code=404, detail="Código não cadastrado no sistema")

    return ChiResponse(
        success=True, codigo=codigo, tipo="equipamento", origem="bot_externo",
        equipamento=EquipamentoOut.model_validate(equipamento),
    )


async def _consultar_ao_vivo(codigo: str, tipo: str) -> str | None:
    """Consulta ao vivo via userbot_consulta_api, ou 404 direto se não configurado."""
    if not userbot_consulta_api.is_configured:
        raise HTTPException(
            status_code=404,
            detail="Código não encontrado no cache (consulta ao vivo indisponível — "
                   "userbot_consulta_api ainda não configurado)",
        )

    query_fn = (
        userbot_consulta_api.query_poste if tipo == "poste"
        else userbot_consulta_api.query_equipamento
    )

    try:
        raw = await asyncio.wait_for(
            query_fn(codigo),
            timeout=settings.bot_terceiro_timeout + 5,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout na consulta ao vivo")

    if raw is None:
        raise HTTPException(status_code=504, detail="Timeout na consulta ao vivo")

    return raw
