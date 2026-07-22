"""API FastAPI para o Bot Integrador."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional
import structlog

from src.config import settings
from src.database.connection import db
from src.userbot import userbot
from src.services.parser import ResponseParser
from src.api.deps import verify_api_key
from src.api.routes.historico import router as historico_router
from src.api.routes.conversa import router as conversa_router
from src.api.routes.chi import router as chi_router
from src.userbot_consulta_api import userbot_consulta_api

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.initialize()
    await userbot_consulta_api.start()
    yield
    await userbot_consulta_api.stop()


# App FastAPI
app = FastAPI(
    title="Bot Integrador API",
    description="API para consulta de postes e equipamentos via Telegram",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(historico_router)
app.include_router(conversa_router)
app.include_router(chi_router)

# Parser
parser = ResponseParser()


# Models
class ConsultaRequest(BaseModel):
    tipo: str
    codigo: str


class Coordenadas(BaseModel):
    latitude: float
    longitude: float


class ConsultaResponse(BaseModel):
    success: bool
    tipo: str
    codigo: str
    dados_brutos: str
    coordenadas: Optional[Coordenadas] = None
    erro: Optional[str] = None



# Endpoints
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/v1/consulta", response_model=ConsultaResponse)
async def consulta(req: ConsultaRequest, api_key: str = Depends(verify_api_key)):
    logger.info(f"Consulta: tipo={req.tipo}, codigo={req.codigo}")
    
    if req.tipo.lower() == "poste":
        resposta = await userbot.query_poste(req.codigo)
    elif req.tipo.lower() == "equipamento":
        resposta = await userbot.query_equipamento(req.codigo)
    else:
        raise HTTPException(status_code=400, detail="Tipo deve ser 'poste' ou 'equipamento'")
    
    if not resposta:
        return ConsultaResponse(
            success=False, tipo=req.tipo, codigo=req.codigo,
            dados_brutos="", erro="Timeout ou falha na consulta"
        )
    
    parsed = parser.parse(resposta)
    
    if not parsed:
        return ConsultaResponse(
            success=False, tipo=req.tipo, codigo=req.codigo,
            dados_brutos=resposta, erro="Não encontrado ou formato não reconhecido"
        )
    
    coords = None
    if parsed.coordenadas:
        coords = Coordenadas(
            latitude=parsed.coordenadas.latitude,
            longitude=parsed.coordenadas.longitude
        )
    
    return ConsultaResponse(
        success=True,
        tipo=str(parsed.tipo.value),
        codigo=parsed.codigo,
        dados_brutos=resposta,
        coordenadas=coords
    )


# Inicialização do servidor
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )
