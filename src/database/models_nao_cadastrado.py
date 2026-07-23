"""
Registro de códigos confirmados como "não cadastrado" no @ReincidenciasBot.

TTL de 7 dias: dentro do prazo, a próxima consulta é respondida direto
daqui (sem reconsultar o bot terceiro). Passado o prazo, reconsulta ao
vivo normalmente — cobre o caso do componente passar a existir depois.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models import Base
from src.database.types import uuid7

TTL_DIAS = 7


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CodigoNaoCadastrado(Base):
    """1 linha por código confirmado como não cadastrado — registro/histórico."""
    __tablename__ = "codigos_nao_cadastrados"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    query_type: Mapped[str] = mapped_column(String(20), nullable=False)  # poste | instalacao

    # Última resposta "não cadastrado" recebida do bot terceiro (texto exato)
    raw_response: Mapped[str] = mapped_column(Text, nullable=False)

    vezes_confirmado: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    primeira_vez: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    ultima_vez: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("code", "query_type", name="uq_codigo_nao_cadastrado"),
        Index("ix_codigos_nao_cadastrados_code_type", "code", "query_type"),
    )

    @property
    def is_fresh(self) -> bool:
        """True se ainda dentro do TTL — responde direto, sem reconsultar."""
        ultima = self.ultima_vez
        if ultima.tzinfo is None:
            ultima = ultima.replace(tzinfo=timezone.utc)
        return ultima >= utcnow() - timedelta(days=TTL_DIAS)

    def __repr__(self) -> str:
        return f"<CodigoNaoCadastrado code={self.code} type={self.query_type} vezes={self.vezes_confirmado}>"
