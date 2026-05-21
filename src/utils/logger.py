"""
Sistema de logging estruturado com structlog.
Logs formatados em JSON para produção e coloridos para desenvolvimento.
"""

import logging
import sys
from pathlib import Path

import structlog

from src.utils.config import get_settings


def setup_logging() -> structlog.BoundLogger:
    """
    Configura e retorna o logger principal da aplicação.
    - Dev: logs coloridos no console
    - Prod: logs em JSON para arquivos
    """
    settings = get_settings()
    
    # Garante que o diretório de logs existe
    settings.logs_path.mkdir(parents=True, exist_ok=True)

    # Nível de log
    log_level = getattr(logging, settings.app_log_level.upper(), logging.INFO)

    # Processadores comuns
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.ExtraAdder(),
    ]

    if settings.is_production:
        # Produção: JSON para arquivo e stdout
        structlog.configure(
            processors=shared_processors + [
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Desenvolvimento: logs coloridos no console
        structlog.configure(
            processors=shared_processors + [
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

    # Configura logging padrão do Python para bibliotecas externas
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    return structlog.get_logger()


def get_logger(name: str = None) -> structlog.BoundLogger:
    """
    Retorna um logger com contexto opcional.
    
    Uso:
        logger = get_logger(__name__)
        logger.info("Mensagem", user_id=123, action="login")
    """
    logger = structlog.get_logger()
    if name:
        logger = logger.bind(module=name)
    return logger
