"""
Endpoint de consulta para o Naeg (DPL) — cálculo de CHI.

Cache-first: busca nas tabelas estruturadas (postes / equipamentos+componentes).
Se não encontrar, consulta ao vivo e persiste antes de responder.

Client ao vivo usado (nessa ordem):
  1. `userbot_consulta_api` (conta dedicada do CHI, "Lucas") — se já
     estiver configurado E com o chat já aberto com o bot terceiro.
  2. Fallback temporário: `userbot` (conta do bot DPL, "Mario") — mesma
     conexão/lock que o bot em tempo real já usa, enquanto a conta
     dedicada do CHI não está pronta. Remover esse fallback assim que
     a conta do Lucas estiver ativa (só desativar não é nem necessário:
     o item 1 passa a ser escolhido automaticamente assim que
     `userbot_consulta_api.is_configured` virar True).

Se nenhum dos dois client estiver disponível, o endpoint funciona só em
modo cache — cache-miss vira 404 direto, sem tentar consulta ao vivo.
Ver API_CHI.md para o contrato completo.
"""
import asyncio

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from src.config import settings
from src.database.connection import db
from src.database.models_estruturados import Equipamento, Poste
from src.parsing.deteccao import is_not_found
from src.services import nao_cadastrado_service, persistencia_estruturada
from src.userbot import userbot
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
    origem: str  # "bot_dpl" (já salvo no nosso banco) | "bot_eqtl" (consulta ao vivo)
    poste: PosteOut | None = None
    equipamento: EquipamentoOut | None = None


@router.get("/{codigo}", response_model=ChiResponse)
async def consultar_chi(
    codigo: str,
    tipo: str = Query(..., pattern="^(poste|equipamento)$"),
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
            success=True, codigo=codigo, tipo="poste", origem="bot_dpl",
            poste=PosteOut.model_validate(poste),
        )

    async with db.session() as session:
        confirmado = await nao_cadastrado_service.buscar_recente(session, codigo, "poste")
    if confirmado:
        raise HTTPException(status_code=404, detail=confirmado.raw_response.strip())

    raw = await _consultar_ao_vivo(codigo, tipo="poste")

    if is_not_found(raw):
        async with db.session() as session:
            await nao_cadastrado_service.registrar(session, codigo, "poste", raw)
        raise HTTPException(status_code=404, detail=raw.strip())

    async with db.session() as session:
        poste = await persistencia_estruturada.salvar_poste(
            session, codigo, raw, origem_client="userbot_consulta_api"
        )

    if not poste:
        raise HTTPException(status_code=404, detail="Código não cadastrado no sistema")

    return ChiResponse(
        success=True, codigo=codigo, tipo="poste", origem="bot_eqtl",
        poste=PosteOut.model_validate(poste),
    )


async def _consultar_equipamento(codigo: str) -> ChiResponse:
    async with db.session() as session:
        stmt = select(Equipamento).where(Equipamento.code == codigo)
        equipamento = (await session.execute(stmt)).scalar_one_or_none()

    if equipamento:
        return ChiResponse(
            success=True, codigo=codigo, tipo="equipamento", origem="bot_dpl",
            equipamento=EquipamentoOut.model_validate(equipamento),
        )

    async with db.session() as session:
        confirmado = await nao_cadastrado_service.buscar_recente(session, codigo, "instalacao")
    if confirmado:
        raise HTTPException(status_code=404, detail=confirmado.raw_response.strip())

    raw = await _consultar_ao_vivo(codigo, tipo="equipamento")

    if is_not_found(raw):
        async with db.session() as session:
            await nao_cadastrado_service.registrar(session, codigo, "instalacao", raw)
        raise HTTPException(status_code=404, detail=raw.strip())

    async with db.session() as session:
        equipamento = await persistencia_estruturada.salvar_equipamento(
            session, codigo, raw, origem_client="userbot_consulta_api"
        )

    if not equipamento:
        raise HTTPException(status_code=404, detail="Código não cadastrado no sistema")

    return ChiResponse(
        success=True, codigo=codigo, tipo="equipamento", origem="bot_eqtl",
        equipamento=EquipamentoOut.model_validate(equipamento),
    )


async def _consultar_ao_vivo(codigo: str, tipo: str) -> str | None:
    """
    Consulta ao vivo.

    TEMPORÁRIO: prioriza a conta do bot DPL (Mario) — a conta dedicada do
    CHI (Lucas) está conectada ao Telegram, mas nunca abriu chat com o
    @ReincidenciasBot, então qualquer consulta por ela trava até dar timeout
    (o bot terceiro nunca manda o prompt de volta). `is_connected` não
    detecta isso — só confirma que a sessão Telethon está online, não que
    a conversa com o bot terceiro funciona de verdade.

    Reverter essa prioridade assim que a conta do Lucas estiver resolvida
    (trocar a ordem do if/elif abaixo).
    """
    if userbot.is_connected:
        client = userbot
    elif userbot_consulta_api.is_configured and userbot_consulta_api.is_connected:
        client = userbot_consulta_api
    else:
        raise HTTPException(
            status_code=404,
            detail="Código não encontrado no cache (consulta ao vivo indisponível — "
                   "nenhum client Telegram conectado)",
        )

    query_fn = client.query_poste if tipo == "poste" else client.query_equipamento

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
