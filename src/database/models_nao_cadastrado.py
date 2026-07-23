"""
Registro de códigos confirmados como "não cadastrado" no @ReincidenciasBot.

Diferente da tentativa anterior (removida): aqui é só um REGISTRO/histórico
— não pula a consulta ao vivo da próxima vez. Toda consulta sempre vai ao
vivo; isso só guarda a última resposta de "não cadastrado" recebida, pra
consulta/auditoria (e pra devolver o texto exato pro chamador da API).
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models import Base
from src.database.types import uuid7


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

    def __repr__(self) -> str:
        return f"<CodigoNaoCadastrado code={self.code} type={self.query_type} vezes={self.vezes_confirmado}>"
