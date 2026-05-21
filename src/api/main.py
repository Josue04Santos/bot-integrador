"""API FastAPI para o Bot Integrador."""
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional
import structlog

from src.config import settings
from src.userbot import userbot
from src.services.parser import ResponseParser

logger = structlog.get_logger()

# App FastAPI
app = FastAPI(
    title="Bot Integrador API",
    description="API para consulta de postes e equipamentos via Telegram",
    version="1.0.0"
)

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


# Auth
async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="API Key inválida")
    return x_api_key


# Lifecycle
@app.on_event("startup")
async def startup():
    logger.info("Iniciando API...")
    await userbot.start()


@app.on_event("shutdown")
async def shutdown():
    logger.info("Encerrando API...")
    await userbot.stop()


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
