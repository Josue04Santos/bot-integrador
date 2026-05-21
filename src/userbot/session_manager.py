"""
Gerenciador de sessões de consulta.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

from src.models.schemas import ConsultaResult, ConsultaStatus, TipoEquipamento
from src.services.parser import ResponseParser
from src.userbot.client import userbot
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConsultaSession:
    """Representa uma sessão de consultas em lote."""
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    user_id: int = 0
    chat_id: int = 0
    codigos: list[str] = field(default_factory=list)
    resultados: list[ConsultaResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    
    @property
    def total(self) -> int:
        return len(self.codigos)
    
    @property
    def processados(self) -> int:
        return len(self.resultados)
    
    @property
    def progresso(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.processados / self.total) * 100
    
    @property
    def is_finished(self) -> bool:
        return self.processados >= self.total


class SessionManager:
    """
    Gerencia múltiplas sessões de consulta simultâneas.
    """
    
    def __init__(self):
        self._sessions: dict[str, ConsultaSession] = {}
        self._active_tasks: dict[str, asyncio.Task] = {}
    
    def create_session(
        self,
        codigos: list[str],
        user_id: int,
        chat_id: int,
    ) -> ConsultaSession:
        """Cria nova sessão de consulta."""
        session = ConsultaSession(
            user_id=user_id,
            chat_id=chat_id,
            codigos=codigos,
        )
        self._sessions[session.id] = session
        logger.info(f"Sessão criada: {session.id} com {len(codigos)} códigos")
        return session
    
    def get_session(self, session_id: str) -> Optional[ConsultaSession]:
        """Retorna sessão pelo ID."""
        return self._sessions.get(session_id)
    
    def get_user_sessions(self, user_id: int) -> list[ConsultaSession]:
        """Retorna sessões de um usuário."""
        return [s for s in self._sessions.values() if s.user_id == user_id]
    
    async def process_session(
        self,
        session: ConsultaSession,
        delay: float = 3.0,
        on_progress: Optional[callable] = None,
    ) -> ConsultaSession:
        """
        Processa todos os códigos de uma sessão.
        
        Args:
            session: Sessão a processar
            delay: Delay entre consultas (segundos)
            on_progress: Callback chamado a cada consulta processada
            
        Returns:
            Sessão atualizada com resultados
        """
        session.started_at = datetime.now()
        
        for i, codigo in enumerate(session.codigos):
            # Consulta o bot
            result = await self._process_single(codigo)
            session.resultados.append(result)
            
            # Callback de progresso
            if on_progress:
                await on_progress(session, result, i + 1)
            
            # Delay entre consultas (exceto última)
            if i < len(session.codigos) - 1:
                await asyncio.sleep(delay)
        
        session.finished_at = datetime.now()
        logger.info(f"Sessão {session.id} finalizada: {session.processados}/{session.total}")
        
        return session
    
    async def _process_single(self, codigo: str) -> ConsultaResult:
        """Processa uma única consulta."""
        result = ConsultaResult(
            codigo=codigo,
            tipo=TipoEquipamento.DESCONHECIDO,
            status=ConsultaStatus.PENDENTE,
            timestamp_envio=datetime.now(),
        )
        
        try:
            # Envia consulta
            result.status = ConsultaStatus.ENVIADA
            response = await userbot.query_reincidencias(codigo)
            
            if response is None:
                result.status = ConsultaStatus.TIMEOUT
                result.erro = "Timeout aguardando resposta"
                return result
            
            # Parse da resposta
            result.timestamp_resposta = datetime.now()
            parsed = ResponseParser.parse(response)
            
            if parsed is None:
                result.status = ConsultaStatus.ERRO
                result.erro = "Não foi possível interpretar a resposta"
                return result
            
            result.data = parsed
            result.tipo = ResponseParser.detect_type(response)
            result.status = ConsultaStatus.RESPONDIDA
            
        except Exception as e:
            result.status = ConsultaStatus.ERRO
            result.erro = str(e)
            logger.error(f"Erro ao processar {codigo}: {e}")
        
        return result
    
    def cancel_session(self, session_id: str) -> bool:
        """Cancela uma sessão em andamento."""
        task = self._active_tasks.get(session_id)
        if task and not task.done():
            task.cancel()
            return True
        return False


# Instância global
session_manager = SessionManager()
