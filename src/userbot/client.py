"""
Cliente Userbot usando Telethon.
"""

import asyncio
from typing import Optional, List
from telethon import TelegramClient, events

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class UserbotClient:
    """Cliente Telegram Userbot."""
    
    def __init__(self):
        self._client: Optional[TelegramClient] = None
        self._connected = False
        self._response_queue: asyncio.Queue = asyncio.Queue()
        self._waiting_response = False
    
    async def start(self) -> bool:
        """Inicia conexão com Telegram."""
        try:
            self._client = TelegramClient(
                str(settings.sessions_path / settings.session_name),
                settings.telegram_api_id,
                settings.telegram_api_hash,
            )
            
            await self._client.start(phone=settings.telegram_phone)
            
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
    
    async def query_poste(self, codigo: str, timeout: float = None) -> Optional[str]:
        """Consulta um POSTE no bot de terceiro (fluxo conversacional)."""
        return await self._send_conversational_query("/PTE", codigo, timeout)
    
    async def query_equipamento(self, codigo: str, timeout: float = None) -> Optional[str]:
        """Consulta um EQUIPAMENTO no bot de terceiro (fluxo conversacional)."""
        return await self._send_conversational_query("/EQP", codigo, timeout)
    
    async def query_reincidencias(self, codigo: str, timeout: float = None, tipo: str = "poste") -> Optional[str]:
        """Consulta genérica (compatibilidade)."""
        if tipo == "equipamento":
            return await self.query_equipamento(codigo, timeout)
        return await self.query_poste(codigo, timeout)
    
    async def _send_conversational_query(self, comando: str, codigo: str, timeout: float = None) -> Optional[str]:
        """
        Envia consulta em fluxo conversacional:
        1. Envia comando (ex: /PTE)
        2. Aguarda prompt do bot
        3. Envia código
        4. Aguarda resposta final
        """
        if not self._connected:
            logger.error("Userbot não conectado")
            return None
        
        timeout = timeout or float(settings.bot_terceiro_timeout)
        
        # Limpa fila
        while not self._response_queue.empty():
            self._response_queue.get_nowait()
        
        try:
            self._waiting_response = True
            
            # ETAPA 1: Envia o comando
            await self._client.send_message(settings.bot_terceiro_username, comando)
            logger.debug(f"Enviado comando: {comando}")
            
            # Aguarda prompt do bot (ex: "Informe o número do poste:")
            try:
                prompt = await asyncio.wait_for(self._response_queue.get(), timeout=timeout)
                logger.debug(f"Prompt recebido: {prompt}")
            except asyncio.TimeoutError:
                logger.warning(f"Timeout esperando prompt após {comando}")
                return None
            
            # ETAPA 2: Envia o código
            await self._client.send_message(settings.bot_terceiro_username, codigo)
            logger.debug(f"Enviado código: {codigo}")
            
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
        """Encerra conexão."""
        if self._client:
            await self._client.disconnect()
            self._connected = False
            logger.info("Userbot desconectado")
    
    @property
    def is_connected(self) -> bool:
        return self._connected


userbot = UserbotClient()
