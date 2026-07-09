"""
Dashboard web — histórico de lotes.

Roda SEPARADO do serviço principal, sem interferir no bot.

Uso:
    cd /home/ti/projetos/dev/bot-integrador
    python -m scripts.dashboard

Acesse: http://localhost:8080/historico
"""
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from src.database.connection import db
from src.api.routes.historico import router
from src.api.routes.conversa import router as conversa_router

app = FastAPI(title="Bot Integrador — Dashboard", docs_url=None, redoc_url=None)
app.include_router(router)
app.include_router(conversa_router)


@app.on_event("startup")
async def startup():
    await db.initialize()


def main():
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")


if __name__ == "__main__":
    main()
