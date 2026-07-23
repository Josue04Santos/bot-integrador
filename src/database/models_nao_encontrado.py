"""
Códigos confirmados como "não cadastrado" no @ReincidenciasBot.

Evita reconsultar ao vivo um código que já sabemos que não existe —
1 linha por (code, query_type), TTL próprio (mais longo que o cache normal,
já que cadastro de rede nova é bem mais raro que atualização de dado
existente). Separada de `code_cache` de propósito: aquela guarda só
respostas válidas, essa guarda o oposto (ausência confirmada).
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models import Base
from src.database.types import uuid7

TTL_DIAS = 30


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CodigoNaoEncontrado(Base):
    """1 linha por código confirmado como não cadastrado no bot terceiro."""
    __tablename__ = "codigos_nao_encontrados"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    query_type: Mapped[str] = mapped_column(String(20), nullable=False)  # poste | instalacao

    # Última vez que confirmamos ao vivo que o código não existe
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("code", "query_type", name="uq_codigo_nao_encontrado"),
        Index("ix_codigos_nao_encontrados_code_type", "code", "query_type"),
    )

    @property
    def is_fresh(self) -> bool:
        """True se ainda dentro do TTL — não precisa reconsultar."""
        checked = self.checked_at
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
        return checked >= utcnow() - timedelta(days=TTL_DIAS)

    def __repr__(self) -> str:
        return f"<CodigoNaoEncontrado code={self.code} type={self.query_type}>"
