"""
Cliente Telegram EXCLUSIVO para consultas vindas da API (ex: CHI/Naeg).

Mesma sessão/protocolo de conversa do userbot do bot DPL
(src/userbot/client.py), mas:
  - conta/número Telegram SEPARADO (settings.consulta_api_telegram_*)
  - linha própria em `telethon_sessions` (SESSION_ID distinto — não
    colide com "userbot")
  - lock próprio — serializa só as chamadas deste client; não precisa
    coordenar com o lock do userbot original, já que são contas
    diferentes conversando de forma independente com o mesmo bot terceiro
  - NÃO usa a fila (`src/dispatcher/queue.py`) — a API é request/response
    síncrono, o handler FastAPI chama query_poste/query_equipamento direto

Se as credenciais (consulta_api_telegram_api_id/hash/phone) estiverem
vazias, `start()` não conecta e loga um aviso — a API funciona em modo
cache-only até a conta real ser configurada.
"""

import asyncio
from enum import Enum
from typing import Optional

from telethon import TelegramClient, events
from telethon.sessions import StringSession
import sqlalchemy as sa

from src.config import settings
from src.database.connection import db
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SQL_LOAD = sa.text(
    "SELECT session_data FROM telethon_sessions WHERE session_id = :sid"
)

_SQL_UPSERT = sa.text("""
    INSERT INTO telethon_sessions (session_id, session_data, updated_at)
    VALUES (:sid, :data, NOW())
    ON CONFLICT (session_id)
    DO UPDATE SET session_data = EXCLUDED.session_data,
                  updated_at   = NOW()
""")


class _Estado(Enum):
    IDLE = "idle"
    AGUARDA_PROMPT = "aguarda_prompt"
    AGUARDA_RESPOSTA = "aguarda_resposta"


_PROMPTS = {
    "/PTE": "informe o número do poste",
    "/EQP": "informe o número do componente",
}


class UserbotConsultaApiClient:
    """Cliente Telegram Userbot dedicado às consultas da API — conta separada."""

    SESSION_ID = "userbot_consulta_api"

    def __init__(self):
        self._client: Optional[TelegramClient] = None
        self._connected = False
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._estado = _Estado.IDLE
        self._consulta_lock = asyncio.Lock()

    @property
    def is_configured(self) -> bool:
        """True se as credenciais da conta dedicada já foram fornecidas."""
        return bool(
            settings.consulta_api_telegram_api_id
            and settings.consulta_api_telegram_api_hash
            and settings.consulta_api_telegram_phone
        )

    # ─────────────────────────────────────────────────────────
    # Persistência da sessão (Postgres) — mesma tabela telethon_sessions,
    # linha própria via SESSION_ID
    # ─────────────────────────────────────────────────────────
    async def _load_session_string(self) -> str:
        async with db.session() as session:
            result = await session.execute(_SQL_LOAD, {"sid": self.SESSION_ID})
            row = result.first()
            if row and row[0]:
                logger.info("Sessão Telethon (consulta API) carregada do Postgres")
                return row[0]
        logger.info("Nenhuma sessão prévia (consulta API) — será criada no primeiro login")
        return ""

    async def _save_session_string(self) -> None:
        if not self._client:
            return
        try:
            session_str = self._client.session.save()
            async with db.session() as session:
                await session.execute(_SQL_UPSERT, {"sid": self.SESSION_ID, "data": session_str})
                await session.commit()
            logger.debug("Sessão Telethon (consulta API) persistida no Postgres")
        except Exception as e:
            logger.error(f"Falha ao salvar sessão (consulta API) no Postgres: {e}")

    # ─────────────────────────────────────────────────────────
    # Ciclo de vida
    # ─────────────────────────────────────────────────────────
    async def start(self) -> bool:
        if not self.is_configured:
            logger.warning(
                "Userbot de consulta API NÃO configurado "
                "(CONSULTA_API_TELEGRAM_API_ID/HASH/PHONE vazios) — "
                "endpoint CHI funcionará só em modo cache, sem fallback ao vivo."
            )
            return False

        try:
            session_str = await self._load_session_string()
            self._client = TelegramClient(
                StringSession(session_str),
                settings.consulta_api_telegram_api_id,
                settings.consulta_api_telegram_api_hash,
            )
            await self._client.start(phone=settings.consulta_api_telegram_phone)
            await self._save_session_string()
            me = await self._client.get_me()
            logger.info(f"Userbot de consulta API conectado como: {me.first_name} (@{me.username})")
            self._setup_handler()
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"Erro ao conectar userbot de consulta API: {e}")
            return False

    def _setup_handler(self) -> None:
        @self._client.on(events.NewMessage(
            from_users=settings.bot_terceiro_username,
            incoming=True,
        ))
        async def on_message(event):
            text = (event.message.text or "").strip()
            if len(text) <= 1:
                return
            if self._estado == _Estado.IDLE:
                logger.warning(f"[consulta_api][IDLE] Mensagem fora de consulta — DESCARTADA: '{text[:80]}'")
                return
            await self._queue.put(text)

    # ─────────────────────────────────────────────────────────
    # API pública
    # ─────────────────────────────────────────────────────────
    async def query_poste(self, codigo: str, timeout: float = None) -> Optional[str]:
        return await self._consultar("/PTE", codigo, timeout)

    async def query_equipamento(self, codigo: str, timeout: float = None) -> Optional[str]:
        return await self._consultar("/EQP", codigo, timeout)

    # ─────────────────────────────────────────────────────────
    # Fluxo conversacional — idêntico ao userbot original, conta diferente
    # ─────────────────────────────────────────────────────────
    async def _consultar(self, comando: str, codigo: str, timeout: float = None) -> Optional[str]:
        async with self._consulta_lock:
            return await self._consultar_sem_lock(comando, codigo, timeout)

    async def _consultar_sem_lock(self, comando: str, codigo: str, timeout: float = None) -> Optional[str]:
        if not self._connected:
            logger.error("Userbot de consulta API não conectado")
            return None

        timeout = timeout or float(settings.bot_terceiro_timeout)
        prompt_esperado = _PROMPTS.get(comando, "")

        await asyncio.sleep(0.8)
        while not self._queue.empty():
            self._queue.get_nowait()

        try:
            self._estado = _Estado.AGUARDA_PROMPT
            await self._client.send_message(settings.bot_terceiro_username, comando)

            deadline = asyncio.get_event_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    logger.warning(f"[consulta_api] TIMEOUT aguardando prompt de '{comando}'")
                    return None
                try:
                    msg = await asyncio.wait_for(self._queue.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    logger.warning("[consulta_api] TIMEOUT aguardando prompt")
                    return None
                if prompt_esperado and prompt_esperado in msg.lower():
                    break

            self._estado = _Estado.AGUARDA_RESPOSTA
            await self._client.send_message(settings.bot_terceiro_username, codigo)

            try:
                resposta = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"[consulta_api] TIMEOUT aguardando resposta para '{codigo}'")
                return None

            partes = [resposta]
            while True:
                try:
                    extra = await asyncio.wait_for(self._queue.get(), timeout=2.5)
                    partes.append(extra)
                except asyncio.TimeoutError:
                    break

            return "\n".join(partes)

        except Exception as e:
            logger.error(f"[consulta_api] Erro inesperado na consulta {comando} {codigo}: {e}")
            if "disconnected" in str(e).lower():
                self._connected = False
            return None

        finally:
            self._estado = _Estado.IDLE

    # ─────────────────────────────────────────────────────────
    # Encerramento
    # ─────────────────────────────────────────────────────────
    async def stop(self) -> None:
        if self._client:
            await self._save_session_string()
            await self._client.disconnect()
            self._connected = False
            logger.info("Userbot de consulta API desconectado")

    @property
    def is_connected(self) -> bool:
        return self._connected


userbot_consulta_api = UserbotConsultaApiClient()
