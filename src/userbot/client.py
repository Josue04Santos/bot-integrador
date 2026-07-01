"""
Cliente Userbot usando Telethon.
Sessão persistida no PostgreSQL (sem SQLite/arquivo local).
"""

import asyncio
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


class UserbotClient:
    """Cliente Telegram Userbot — sessão no PostgreSQL."""

    SESSION_ID = "userbot"  # chave fixa na tabela telethon_sessions

    def __init__(self):
        self._client: Optional[TelegramClient] = None
        self._connected = False
        self._response_queue: asyncio.Queue = asyncio.Queue()
        self._waiting_response = False

    # ─────────────────────────────────────────────────────────
    # Persistência da sessão (Postgres)
    # ─────────────────────────────────────────────────────────
    async def _ensure_table(self) -> None:
        """Garante que a tabela telethon_sessions existe."""
        async with db.session() as session:
            await session.execute(sa.text(_DDL_TELETHON_SESSIONS))
            await session.commit()

    async def _load_session_string(self) -> str:
        """Carrega string da sessão do Postgres (ou '' se não existir)."""
        async with db.session() as session:
            result = await session.execute(_SQL_LOAD, {"sid": self.SESSION_ID})
            row = result.first()
            if row and row[0]:
                logger.info("Sessão Telethon carregada do Postgres")
                return row[0]
        logger.info("Nenhuma sessão prévia — será criada no primeiro login")
        return ""

    async def _save_session_string(self) -> None:
        """Salva a string da sessão atual no Postgres."""
        if not self._client:
            return
        try:
            session_str = self._client.session.save()
            async with db.session() as session:
                await session.execute(
                    _SQL_UPSERT,
                    {"sid": self.SESSION_ID, "data": session_str},
                )
                await session.commit()
            logger.debug("Sessão Telethon persistida no Postgres")
        except Exception as e:
            logger.error(f"Falha ao salvar sessão no Postgres: {e}")

    # ─────────────────────────────────────────────────────────
    # Ciclo de vida
    # ─────────────────────────────────────────────────────────
    async def start(self) -> bool:
        """Inicia conexão com Telegram (sessão no Postgres)."""
        try:
            # 1) Garante tabela + carrega sessão existente
            await self._ensure_table()
            session_str = await self._load_session_string()

            # 2) Cria cliente com StringSession (sem arquivo .session)
            self._client = TelegramClient(
                StringSession(session_str),
                settings.telegram_api_id,
                settings.telegram_api_hash,
            )

            # 3) Login (interativo apenas se sessão vazia/inválida)
            await self._client.start(phone=settings.telegram_phone)

            # 4) Salva sessão (pode ter sido criada/atualizada no login)
            await self._save_session_string()

            me = await self._client.get_me()
            logger.info(f"Userbot conectado como: {me.first_name} (@{me.username})")

            self._setup_handlers()
            self._connected = True
            return True

        except Exception as e:
            logger.error(f"Erro ao conectar userbot: {e}")
            return False

    def _setup_handlers(self) -> None:
        """Configura handlers de mensagens."""
        @self._client.on(events.NewMessage(
            from_users=settings.bot_terceiro_username,
            incoming=True,
        ))
        async def handle_bot_response(event):
            if self._waiting_response:
                text = event.message.text or ""
                # Ignora mensagens de 1 char (indicadores visuais como ▼)
                if len(text) > 1:
                    await self._response_queue.put(text)
                    logger.debug(f"Msg recebida ({len(text)} chars): {text[:50]}...")

    # ─────────────────────────────────────────────────────────
    # API pública de consultas (inalterada)
    # ─────────────────────────────────────────────────────────
    async def query_poste(self, codigo: str, timeout: float = None) -> Optional[str]:
        """Consulta um POSTE no bot de terceiro (fluxo conversacional)."""
        return await self._send_conversational_query("/PTE", codigo, timeout)

    async def query_equipamento(self, codigo: str, timeout: float = None) -> Optional[str]:
        """Consulta um EQUIPAMENTO no bot de terceiro (fluxo conversacional)."""
        return await self._send_conversational_query("/EQP", codigo, timeout)

    async def query_reincidencias(
        self, codigo: str, timeout: float = None, tipo: str = "poste"
    ) -> Optional[str]:
        """Consulta genérica (compatibilidade)."""
        if tipo == "equipamento":
            return await self.query_equipamento(codigo, timeout)
        return await self.query_poste(codigo, timeout)

    # Prompts exatos que o bot externo envia para cada comando
    _PROMPTS_ESPERADOS = {
        "/PTE": "informe o número do poste",
        "/EQP": "informe o número do componente",
    }

    async def _send_conversational_query(
        self, comando: str, codigo: str, timeout: float = None
    ) -> Optional[str]:
        """
        Envia consulta em fluxo conversacional:
        1. Envia comando (ex: /PTE)
        2. Aguarda e VALIDA o prompt do bot antes de enviar o código
        3. Envia código apenas quando o bot está esperando
        4. Aguarda resposta final
        """
        if not self._connected:
            logger.error("Userbot não conectado")
            return None

        timeout = timeout or float(settings.bot_terceiro_timeout)
        prompt_esperado = self._PROMPTS_ESPERADOS.get(comando, "")

        # Aguarda mensagens atrasadas e descarta tudo antes de começar
        await asyncio.sleep(0.8)
        while not self._response_queue.empty():
            dropped = self._response_queue.get_nowait()
            logger.debug(f"Fila limpa — descartado: {str(dropped)[:40]}")

        try:
            self._waiting_response = True

            # ETAPA 1: Envia o comando
            await self._client.send_message(settings.bot_terceiro_username, comando)
            logger.debug(f"Enviado comando: {comando}")

            # ETAPA 2: Aguarda e VALIDA o prompt
            # Descarta mensagens que não sejam o prompt esperado (residuais)
            prompt_recebido = False
            deadline = asyncio.get_event_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    logger.warning(f"Timeout aguardando prompt de '{comando}'")
                    return None
                try:
                    msg = await asyncio.wait_for(
                        self._response_queue.get(), timeout=remaining
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout aguardando prompt de '{comando}'")
                    return None

                if prompt_esperado and prompt_esperado in msg.lower():
                    logger.debug(f"Prompt validado: '{msg.strip()}'")
                    prompt_recebido = True
                    break
                else:
                    # Mensagem inesperada — descarta e aguarda o prompt correto
                    logger.warning(
                        f"Mensagem inesperada descartada (aguardando prompt): "
                        f"'{msg[:60]}'"
                    )

            if not prompt_recebido:
                return None

            # ETAPA 3: Prompt confirmado — agora é seguro enviar o código
            await self._client.send_message(settings.bot_terceiro_username, codigo)
            logger.debug(f"Código enviado após prompt validado: {codigo}")

            # ETAPA 3: Coleta resposta final (pode ser múltiplas mensagens)
            messages: List[str] = []
            wait_time = 2.5  # Tempo para aguardar mais mensagens

            # Aguarda primeira resposta
            try:
                first = await asyncio.wait_for(self._response_queue.get(), timeout=timeout)
                messages.append(first)
                logger.debug(f"Primeira resposta: {len(first)} chars")
            except asyncio.TimeoutError:
                logger.warning(f"Timeout esperando resposta para código: {codigo}")
                return None

            # Continua coletando mensagens adicionais
            while True:
                try:
                    msg = await asyncio.wait_for(self._response_queue.get(), timeout=wait_time)
                    messages.append(msg)
                    logger.debug(f"Msg adicional: {len(msg)} chars")
                except asyncio.TimeoutError:
                    break

            # Junta todas as mensagens
            full_response = "\n".join(messages)
            logger.info(f"Resposta completa: {len(messages)} msgs, {len(full_response)} chars")
            return full_response

        except Exception as e:
            logger.error(f"Erro na consulta: {e}")
            return None
        finally:
            self._waiting_response = False

    async def _send_query(self, mensagem: str, timeout: float = None) -> Optional[str]:
        """Envia mensagem simples (para comandos como /Menu)."""
        if not self._connected:
            logger.error("Userbot não conectado")
            return None

        timeout = timeout or float(settings.bot_terceiro_timeout)

        while not self._response_queue.empty():
            self._response_queue.get_nowait()

        try:
            self._waiting_response = True

            await self._client.send_message(settings.bot_terceiro_username, mensagem)
            logger.debug(f"Enviado: {mensagem}")

            messages: List[str] = []
            wait_time = 2.0

            try:
                first = await asyncio.wait_for(self._response_queue.get(), timeout=timeout)
                messages.append(first)
            except asyncio.TimeoutError:
                return None

            while True:
                try:
                    msg = await asyncio.wait_for(self._response_queue.get(), timeout=wait_time)
                    messages.append(msg)
                except asyncio.TimeoutError:
                    break

            return "\n".join(messages)

        except Exception as e:
            logger.error(f"Erro: {e}")
            return None
        finally:
            self._waiting_response = False

    async def stop(self) -> None:
        """Encerra conexão (salva sessão antes)."""
        if self._client:
            # Salva sessão atualizada (peer cache, etc) antes de desconectar
            await self._save_session_string()
            await self._client.disconnect()
            self._connected = False
            logger.info("Userbot desconectado")

    @property
    def is_connected(self) -> bool:
        return self._connected


userbot = UserbotClient()
