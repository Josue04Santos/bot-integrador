"""Dependências compartilhadas entre os routers da API."""
from fastapi import Header, HTTPException, Query

from src.config import settings


async def verify_api_key(
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None),
) -> str:
    """
    Aceita a chave via header `X-API-Key` (uso normal/programático) OU via
    query param `?api_key=` (permite um link direto no navegador, sem
    precisar configurar header).
    """
    chave = x_api_key or api_key
    if chave != settings.api_key:
        raise HTTPException(status_code=401, detail="API Key inválida ou ausente")
    return chave
