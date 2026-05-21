"""
Processador de consultas em lote.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Union

from src.models.schemas import (
    ConsultaResult,
    ConsultaStatus,
    PosteData,
    InstalacaoData,
)
from src.services.parser import ResponseParser
from src.services.kml_generator import KMLGenerator
from src.userbot.client import userbot
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class QueryProcessor:
    """
    Processa lotes de consultas ao @ReincidenciasBot.
    
    Funcionalidades:
    - Processa lista de códigos sequencialmente
    - Respeita delay entre consultas
    - Gera KML com resultados
    - Callbacks de progresso
    """
    
    def __init__(
        self,
        delay: float = None,
        timeout: float = None,
    ):
        """
        Inicializa o processador.
        
        Args:
            delay: Delay entre consultas (segundos)
            timeout: Timeout por consulta (segundos)
        """
        self.delay = delay if delay is not None else settings.delay_between_queries
        self.timeout = timeout if timeout is not None else settings.bot_terceiro_timeout
        self._is_running = False
        self._should_stop = False
    
    async def process_batch(
        self,
        codigos: list[str],
        on_progress: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
        generate_kml: bool = True,
        kml_filename: Optional[str] = None,
    ) -> dict:
        """
        Processa um lote de códigos.
        
        Args:
            codigos: Lista de códigos para consultar
            on_progress: Callback(resultado, atual, total) chamado a cada consulta
            on_complete: Callback(resultados) chamado ao finalizar
            generate_kml: Se deve gerar arquivo KML
            kml_filename: Nome do arquivo KML (opcional)
            
        Returns:
            Dict com estatísticas e resultados
        """
        if self._is_running:
            raise RuntimeError("Já existe um processamento em andamento")
        
        self._is_running = True
        self._should_stop = False
        
        resultados: list[ConsultaResult] = []
        items_para_kml: list[Union[PosteData, InstalacaoData]] = []
        
        started_at = datetime.now()
        total = len(codigos)
        
        logger.info(f"Iniciando processamento de {total} códigos")
        
        try:
            for i, codigo in enumerate(codigos, 1):
                if self._should_stop:
                    logger.info("Processamento cancelado pelo usuário")
                    break
                
                # Processa código
                resultado = await self._process_single(codigo)
                resultados.append(resultado)
                
                # Adiciona ao KML se tiver dados válidos
                if resultado.data and resultado.data.coordenadas:
                    items_para_kml.append(resultado.data)
                
                # Callback de progresso
                if on_progress:
                    try:
                        await on_progress(resultado, i, total)
                    except Exception as e:
                        logger.error(f"Erro no callback de progresso: {e}")
                
                # Delay entre consultas (exceto última)
                if i < total and not self._should_stop:
                    await asyncio.sleep(self.delay)
            
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            
            # Gera KML
            kml_path = None
            if generate_kml and items_para_kml:
                if not kml_filename:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    kml_filename = f"consulta_{timestamp}.kml"
                
                kml_path = KMLGenerator.generate(
                    items_para_kml,
                    filename=kml_filename,
                    output_dir=settings.output_path,
                )
            
            # Estatísticas
            stats = self._calculate_stats(resultados, duration)
            stats["kml_path"] = str(kml_path) if kml_path else None
            stats["kml_items"] = len(items_para_kml)
            
            # Callback de conclusão
            if on_complete:
                try:
                    await on_complete(resultados, stats)
                except Exception as e:
                    logger.error(f"Erro no callback de conclusão: {e}")
            
            logger.info(
                f"Processamento finalizado: {stats['sucesso']}/{total} "
                f"em {duration:.1f}s"
            )
            
            return {
                "resultados": resultados,
                "stats": stats,
                "kml_path": kml_path,
            }
            
        finally:
            self._is_running = False
    
    async def _process_single(self, codigo: str) -> ConsultaResult:
        """Processa uma única consulta."""
        resultado = ConsultaResult(
            codigo=codigo,
            status=ConsultaStatus.PENDENTE,
            timestamp_envio=datetime.now(),
        )
        
        try:
            # Verifica conexão do userbot
            if not userbot.is_connected:
                resultado.status = ConsultaStatus.ERRO
                resultado.erro = "Userbot não conectado"
                return resultado
            
            # Envia consulta
            resultado.status = ConsultaStatus.ENVIADA
            response = await userbot.query_reincidencias(codigo, self.timeout)
            
            if response is None:
                resultado.status = ConsultaStatus.TIMEOUT
                resultado.erro = "Timeout aguardando resposta"
                return resultado
            
            resultado.timestamp_resposta = datetime.now()
            
            # Parse da resposta
            parsed = ResponseParser.parse(response)
            
            if parsed is None:
                resultado.status = ConsultaStatus.ERRO
                resultado.erro = "Resposta não reconhecida"
                return resultado
            
            resultado.data = parsed
            resultado.tipo = ResponseParser.detect_type(response)
            resultado.status = ConsultaStatus.RESPONDIDA
            
            logger.debug(
                f"Código {codigo}: {resultado.tipo.value} - "
                f"{resultado.tempo_resposta:.2f}s"
            )
            
        except Exception as e:
            resultado.status = ConsultaStatus.ERRO
            resultado.erro = str(e)
            logger.error(f"Erro ao processar {codigo}: {e}")
        
        return resultado
    
    def _calculate_stats(
        self,
        resultados: list[ConsultaResult],
        duration: float,
    ) -> dict:
        """Calcula estatísticas do processamento."""
        total = len(resultados)
        sucesso = sum(1 for r in resultados if r.status == ConsultaStatus.RESPONDIDA)
        timeout = sum(1 for r in resultados if r.status == ConsultaStatus.TIMEOUT)
        erro = sum(1 for r in resultados if r.status == ConsultaStatus.ERRO)
        
        tempos = [
            r.tempo_resposta for r in resultados 
            if r.tempo_resposta is not None
        ]
        
        return {
            "total": total,
            "sucesso": sucesso,
            "timeout": timeout,
            "erro": erro,
            "taxa_sucesso": (sucesso / total * 100) if total > 0 else 0,
            "duracao_total": duration,
            "tempo_medio": sum(tempos) / len(tempos) if tempos else 0,
            "tempo_min": min(tempos) if tempos else 0,
            "tempo_max": max(tempos) if tempos else 0,
        }
    
    def stop(self) -> None:
        """Solicita parada do processamento."""
        self._should_stop = True
        logger.info("Solicitação de parada enviada")
    
    @property
    def is_running(self) -> bool:
        """Retorna se há processamento em andamento."""
        return self._is_running
