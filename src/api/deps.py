"""Dependências compartilhadas entre os routers da API."""
from fastapi import Header, HTTPException

from src.config import settings


async def verify_api_key(x_api_key: str = Header(...)) -> str:
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="API Key inválida")
    return x_api_key
