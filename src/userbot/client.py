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
from typing import Optional, List, TYPE_CHECKING

from telethon import TelegramClient, events
from telethon.sessions import StringSession
import sqlalchemy as sa

from src.config import settings
from src.database.connection import db
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from aiogram import Bot

logger = get_logger(__name__)

# Intervalo do health-check de conexão e cooldown entre alertas repetidos
_HEALTH_CHECK_INTERVAL = 20.0  # segundos


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
        self._alert_bot: Optional["Bot"] = None
        self._alert_sent = False
        self._health_task: Optional[asyncio.Task] = None
        # Serializa chamadas concorrentes a _consultar — o worker (tempo real)
        # e o scheduler de auto-refresh (madrugada) compartilham a mesma conversa
        # com o bot externo, que só suporta 1 interação por vez.
        self._consulta_lock = asyncio.Lock()

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
    async def start(self, alert_bot: Optional["Bot"] = None) -> bool:
        self._alert_bot = alert_bot
        try:
            await self._ensure_table()
            session_str = await self._load_session_string()
            self._client = TelegramClient(
                StringSession(session_str),
                settings.bot_telegram_api_id,
                settings.bot_telegram_api_hash,
            )
            await self._client.start(phone=settings.bot_telegram_phone)
            await self._save_session_string()
            me = await self._client.get_me()
            logger.info(f"Userbot conectado como: {me.first_name} (@{me.username})")
            self._setup_handler()
            self._connected = True
            self._health_task = asyncio.create_task(self._watch_connection())
            return True
        except Exception as e:
            logger.error(f"Erro ao conectar userbot: {e}")
            return False

    async def _alert(self, text: str) -> None:
        """Envia uma mensagem de alerta para os super admins configurados."""
        if not self._alert_bot:
            return
        for admin_id in settings.super_admin_ids:
            try:
                await self._alert_bot.send_message(admin_id, text)
            except Exception:
                logger.exception(f"Falha ao enviar alerta de conexão para admin {admin_id}")

    async def _alert_disconnected(self, contexto: str = "") -> None:
        """Dispara o alerta de desconexão uma única vez por episódio (evita spam)."""
        if self._alert_sent:
            return
        self._alert_sent = True
        sufixo = f" ({contexto})" if contexto else ""
        await self._alert(
            f"⚠️ <b>Userbot desconectado do Telegram{sufixo}</b>\n"
            f"Consultas ao bot externo estão indisponíveis até a reconexão."
        )

    async def _watch_connection(self) -> None:
        """
        Loop de health-check: detecta queda de conexão, tenta reconectar
        automaticamente e alerta os admins caso a queda persista.
        """
        while True:
            await asyncio.sleep(_HEALTH_CHECK_INTERVAL)
            if not self._client:
                continue

            if self._client.is_connected():
                self._connected = True
                if self._alert_sent:
                    logger.info("Userbot reconectado ao Telegram")
                    await self._alert("✅ Userbot reconectado ao Telegram.")
                    self._alert_sent = False
                continue

            logger.warning("Health-check: userbot desconectado — tentando reconectar")
            self._connected = False
            try:
                await self._client.connect()
            except Exception as e:
                logger.error(f"Falha ao tentar reconectar userbot: {e}")

            if self._client.is_connected():
                self._connected = True
                logger.info("Reconexão automática bem-sucedida")
                if self._alert_sent:
                    await self._alert("✅ Userbot reconectado ao Telegram.")
                    self._alert_sent = False
            else:
                await self._alert_disconnected("reconexão automática falhou")

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
                logger.warning(f"[IDLE] Mensagem chegou fora de consulta — DESCARTADA: '{text[:80]}'")
                return

            logger.info(f"[{self._estado.value}] Mensagem enfileirada ({len(text)} chars)")
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

        Serializado por _consulta_lock: o worker (tempo real) e o scheduler
        de auto-refresh nunca podem conversar com o bot externo ao mesmo tempo.
        """
        async with self._consulta_lock:
            return await self._consultar_sem_lock(comando, codigo, timeout)

    async def _consultar_sem_lock(self, comando: str, codigo: str, timeout: float = None) -> Optional[str]:
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
            logger.info(f">>> ENVIANDO COMANDO  : '{comando}'  (código a consultar: {codigo})")

            await self._client.send_message(settings.bot_terceiro_username, comando)

            # Aguarda o prompt correto — descarta qualquer outra mensagem
            deadline = asyncio.get_event_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    logger.warning(f"!!! TIMEOUT AGUARDANDO PROMPT de '{comando}' — bot externo não respondeu")
                    return None

                try:
                    msg = await asyncio.wait_for(self._queue.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    logger.warning(f"!!! TIMEOUT AGUARDANDO PROMPT — sem resposta do bot externo")
                    return None

                logger.info(f"<<< RECEBIDO (estado={self._estado.value}): '{msg.strip()}'")

                if prompt_esperado and prompt_esperado in msg.lower():
                    logger.info(f"    ✔ Prompt correto reconhecido — avançando para envio do código")
                    break
                else:
                    logger.warning(f"    ✘ Mensagem inesperada — descartando e aguardando prompt correto")

            # ── INTERAÇÃO 2: Código → Dados ────────────────────────────────
            self._estado = _Estado.AGUARDA_RESPOSTA
            logger.info(f">>> ENVIANDO CÓDIGO   : '{codigo}'")

            await self._client.send_message(settings.bot_terceiro_username, codigo)

            # Aguarda a resposta principal
            try:
                resposta = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                logger.info(f"<<< RECEBIDO (estado={self._estado.value}): '{resposta[:120].strip()}' ({'...' if len(resposta) > 120 else ''})")
            except asyncio.TimeoutError:
                logger.warning(f"!!! TIMEOUT AGUARDANDO RESPOSTA para código '{codigo}'")
                return None

            # Coleta mensagens adicionais (caso o bot envie em partes)
            partes = [resposta]
            while True:
                try:
                    extra = await asyncio.wait_for(self._queue.get(), timeout=2.5)
                    partes.append(extra)
                    logger.info(f"<<< RECEBIDO (parte {len(partes)}): '{extra[:80].strip()}'")
                except asyncio.TimeoutError:
                    break

            resultado = "\n".join(partes)
            logger.info(f"    ✔ Consulta concluída: {len(partes)} parte(s), {len(resultado)} chars")
            return resultado

        except Exception as e:
            logger.error(f"Erro inesperado na consulta {comando} {codigo}: {e}")
            if "disconnected" in str(e).lower():
                self._connected = False
                asyncio.create_task(self._alert_disconnected(f"falha ao enviar {comando} {codigo}"))
            return None

        finally:
            self._estado = _Estado.IDLE
            logger.info(f"--- ESTADO → IDLE  (fim de {comando} {codigo}) ---")

    # ─────────────────────────────────────────────────────────
    # Encerramento
    # ─────────────────────────────────────────────────────────
    async def stop(self) -> None:
        if self._health_task:
            self._health_task.cancel()
            self._health_task = None
        if self._client:
            await self._save_session_string()
            await self._client.disconnect()
            self._connected = False
            logger.info("Userbot desconectado")

    @property
    def is_connected(self) -> bool:
        return self._connected


userbot = UserbotClient()
