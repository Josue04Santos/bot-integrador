"""
Cliente Userbot usando Telethon.
Sessão persistida no PostgreSQL (sem SQLite/arquivo local).

Fluxo conversacional com o @ReincidenciasBot (2 interações):

  INTERAÇÃO 1 — Poste (/PTE):
    Nós  →  /PTE
    Bot  ←  "Informe o número do poste:"
    Nós  →  {codigo}
    Bot  ←  dados do poste  (ou "Poste não cadastrado.")

  INTERAÇÃO 2 — Equipamento (/EQP):
    Nós  →  /EQP
    Bot  ←  "Informe o número do componente:"
    Nós  →  {codigo}
    Bot  ←  dados do equipamento  (ou "Componente não cadastrado.")

Estado da conversa rastreado explicitamente:
    IDLE → AGUARDA_PROMPT → AGUARDA_RESPOSTA → IDLE
"""

import asyncio
from enum import Enum
from typing import Optional, List

from telethon import TelegramClient, events
from telethon.sessions import StringSession
import sqlalchemy as sa

from src.config import settings
from src.database.connection import db
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
# DDL da tabela de sessões (idempotente)
# ─────────────────────────────────────────────────────────────
_DDL_TELETHON_SESSIONS = """
CREATE TABLE IF NOT EXISTS telethon_sessions (
    session_id   VARCHAR(100) PRIMARY KEY,
    session_data TEXT         NOT NULL,
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
"""

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
    """Estado da conversa com o bot externo."""
    IDLE             = "idle"
    AGUARDA_PROMPT   = "aguarda_prompt"    # enviamos /PTE ou /EQP, aguardando "Informe..."
    AGUARDA_RESPOSTA = "aguarda_resposta"  # enviamos o código, aguardando dados


# Prompts exatos que o bot externo envia (texto em minúsculo para comparação)
_PROMPTS = {
    "/PTE": "informe o número do poste",
    "/EQP": "informe o número do componente",
}


class UserbotClient:
    """Cliente Telegram Userbot — sessão no PostgreSQL."""

    SESSION_ID = "userbot"

    def __init__(self):
        self._client: Optional[TelegramClient] = None
        self._connected = False
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._estado = _Estado.IDLE

    # ─────────────────────────────────────────────────────────
    # Persistência da sessão (Postgres)
    # ─────────────────────────────────────────────────────────
    async def _ensure_table(self) -> None:
        async with db.session() as session:
            await session.execute(sa.text(_DDL_TELETHON_SESSIONS))
            await session.commit()

    async def _load_session_string(self) -> str:
        async with db.session() as session:
            result = await session.execute(_SQL_LOAD, {"sid": self.SESSION_ID})
            row = result.first()
            if row and row[0]:
                logger.info("Sessão Telethon carregada do Postgres")
                return row[0]
        logger.info("Nenhuma sessão prévia — será criada no primeiro login")
        return ""

    async def _save_session_string(self) -> None:
        if not self._client:
            return
        try:
            session_str = self._client.session.save()
            async with db.session() as session:
                await session.execute(_SQL_UPSERT, {"sid": self.SESSION_ID, "data": session_str})
                await session.commit()
            logger.debug("Sessão Telethon persistida no Postgres")
        except Exception as e:
            logger.error(f"Falha ao salvar sessão no Postgres: {e}")

    # ─────────────────────────────────────────────────────────
    # Ciclo de vida
    # ─────────────────────────────────────────────────────────
    async def start(self) -> bool:
        try:
            await self._ensure_table()
            session_str = await self._load_session_string()
            self._client = TelegramClient(
                StringSession(session_str),
                settings.telegram_api_id,
                settings.telegram_api_hash,
            )
            await self._client.start(phone=settings.telegram_phone)
            await self._save_session_string()
            me = await self._client.get_me()
            logger.info(f"Userbot conectado como: {me.first_name} (@{me.username})")
            self._setup_handler()
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"Erro ao conectar userbot: {e}")
            return False

    def _setup_handler(self) -> None:
        """
        Handler de mensagens do bot externo.

        Só aceita mensagens quando NÃO estamos em IDLE.
        Isso garante que mensagens atrasadas ou fora de hora
        sejam descartadas silenciosamente.
        """
        @self._client.on(events.NewMessage(
            from_users=settings.bot_terceiro_username,
            incoming=True,
        ))
        async def on_message(event):
            text = (event.message.text or "").strip()

            # Ignora mensagens vazias ou indicadores visuais (▼, etc.)
            if len(text) <= 1:
                return

            if self._estado == _Estado.IDLE:
                # Fora de uma consulta — descarta qualquer mensagem atrasada
                logger.debug(f"[IDLE] Mensagem descartada do bot externo: '{text[:50]}'")
                return

            logger.debug(f"[{self._estado.value}] Mensagem recebida ({len(text)} chars): '{text[:60]}'")
            await self._queue.put(text)

    # ─────────────────────────────────────────────────────────
    # API pública
    # ─────────────────────────────────────────────────────────
    async def query_poste(self, codigo: str, timeout: float = None) -> Optional[str]:
        return await self._consultar("/PTE", codigo, timeout)

    async def query_equipamento(self, codigo: str, timeout: float = None) -> Optional[str]:
        return await self._consultar("/EQP", codigo, timeout)

    async def query_reincidencias(self, codigo: str, timeout: float = None, tipo: str = "poste") -> Optional[str]:
        if tipo == "equipamento":
            return await self.query_equipamento(codigo, timeout)
        return await self.query_poste(codigo, timeout)

    # ─────────────────────────────────────────────────────────
    # Fluxo conversacional
    # ─────────────────────────────────────────────────────────
    async def _consultar(self, comando: str, codigo: str, timeout: float = None) -> Optional[str]:
        """
        Executa a consulta em 2 interações com o bot externo.

        INTERAÇÃO 1 — Comando → Prompt:
            Enviamos:  /PTE  ou  /EQP
            Esperamos: "Informe o número do poste:"
                    ou "Informe o número do componente:"
            Validamos: texto do prompt antes de avançar

        INTERAÇÃO 2 — Código → Dados:
            Enviamos:  o código (ex: 1005792)
            Esperamos: dados completos da instalação/poste
                    ou mensagem de erro ("não cadastrado")
        """
        if not self._connected:
            logger.error("Userbot não conectado")
            return None

        timeout = timeout or float(settings.bot_terceiro_timeout)
        prompt_esperado = _PROMPTS.get(comando, "")

        # ── Garante estado limpo antes de começar ──────────────────────────
        # Aguarda mensagens residuais em trânsito e as descarta
        await asyncio.sleep(0.8)
        descartadas = 0
        while not self._queue.empty():
            self._queue.get_nowait()
            descartadas += 1
        if descartadas:
            logger.debug(f"Fila limpa: {descartadas} mensagem(ns) residual(is) descartada(s)")

        try:
            # ── INTERAÇÃO 1: Comando → Prompt ──────────────────────────────
            self._estado = _Estado.AGUARDA_PROMPT
            logger.info(f"[AGUARDA_PROMPT] Enviando: {comando} (código: {codigo})")

            await self._client.send_message(settings.bot_terceiro_username, comando)

            # Aguarda o prompt correto — descarta qualquer outra mensagem
            deadline = asyncio.get_event_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    logger.warning(f"[AGUARDA_PROMPT] Timeout — bot externo não enviou prompt para {comando}")
                    return None

                try:
                    msg = await asyncio.wait_for(self._queue.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    logger.warning(f"[AGUARDA_PROMPT] Timeout — sem resposta do bot externo")
                    return None

                if prompt_esperado and prompt_esperado in msg.lower():
                    logger.info(f"[AGUARDA_PROMPT] Prompt validado: '{msg.strip()}'")
                    break
                else:
                    # Mensagem inesperada — pode ser resíduo de consulta anterior
                    logger.warning(f"[AGUARDA_PROMPT] Mensagem inesperada descartada: '{msg[:60]}'")

            # ── INTERAÇÃO 2: Código → Dados ────────────────────────────────
            self._estado = _Estado.AGUARDA_RESPOSTA
            logger.info(f"[AGUARDA_RESPOSTA] Enviando código: {codigo}")

            await self._client.send_message(settings.bot_terceiro_username, codigo)

            # Aguarda a resposta principal
            try:
                resposta = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                logger.info(f"[AGUARDA_RESPOSTA] Resposta recebida: {len(resposta)} chars")
            except asyncio.TimeoutError:
                logger.warning(f"[AGUARDA_RESPOSTA] Timeout — bot externo não respondeu para {codigo}")
                return None

            # Coleta mensagens adicionais (caso o bot envie em partes)
            partes = [resposta]
            while True:
                try:
                    extra = await asyncio.wait_for(self._queue.get(), timeout=2.5)
                    partes.append(extra)
                    logger.debug(f"[AGUARDA_RESPOSTA] Mensagem adicional: {len(extra)} chars")
                except asyncio.TimeoutError:
                    break

            resultado = "\n".join(partes)
            logger.info(f"Consulta concluída: {len(partes)} parte(s), {len(resultado)} chars total")
            return resultado

        except Exception as e:
            logger.error(f"Erro inesperado na consulta {comando} {codigo}: {e}")
            return None

        finally:
            # Sempre volta ao IDLE — mensagens fora de hora são descartadas
            self._estado = _Estado.IDLE
            logger.debug(f"Estado → IDLE (após {comando} {codigo})")

    # ─────────────────────────────────────────────────────────
    # Encerramento
    # ─────────────────────────────────────────────────────────
    async def stop(self) -> None:
        if self._client:
            await self._save_session_string()
            await self._client.disconnect()
            self._connected = False
            logger.info("Userbot desconectado")

    @property
    def is_connected(self) -> bool:
        return self._connected


userbot = UserbotClient()
