"""Camada de banco de dados."""
from src.database.connection import db, get_session, DatabaseManager
from src.database.models import (
    Base,
    AuthorizedUser,
    QueryBatch,
    NetworkQuery,
    Meter,
    KmlExport,
    AgentRun,
    CodeCache,
)
from src.database.models_estruturados import (
    Poste,
    Equipamento,
    Componente,
)
from src.database.models_legado import (
    TelethonSession,
    UsuarioLegado,
)
from src.database.models_nao_cadastrado import CodigoNaoCadastrado
from src.database.types import uuid7, uuid7_timestamp

__all__ = [
    # Connection
    "db",
    "get_session",
    "DatabaseManager",
    # Models
    "Base",
    "AuthorizedUser",
    "QueryBatch",
    "NetworkQuery",
    "Meter",
    "KmlExport",
    "AgentRun",
    "CodeCache",
    # Models estruturados
    "Poste",
    "Equipamento",
    "Componente",
    # Legado
    "TelethonSession",
    "UsuarioLegado",
    # Não cadastrados
    "CodigoNaoCadastrado",
    # Utils
    "uuid7",
    "uuid7_timestamp",
]
