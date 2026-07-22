"""
Tabelas estruturadas — fonte de verdade para dados de rede elétrica.

Diferente de `network_queries`/`code_cache` (histórico bruto/cache do texto
retornado pelo bot terceiro), estas tabelas guardam o resultado JÁ PARSEADO
das consultas de poste e equipamento, prontas para consumo via API (ex: CHI).

Tabelas:
    - postes        → 1 linha por código de poste (upsert)
    - equipamentos   → 1 linha por código de equipamento/instalação (upsert)
    - componentes    → chaves a montante de um equipamento (FU/CF/RG/DJ/SE),
                       substituídas por completo a cada nova consulta do pai
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models import Base
from src.database.types import uuid7


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================================
# POSTES — 1 linha por código, dado estruturado do @ReincidenciasBot
# ============================================================================
class Poste(Base):
    """Dados estruturados de um poste (upsert por `code`)."""
    __tablename__ = "postes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    alimentadores: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    cabos_mt: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    cabos_bt: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    estruturas_mt: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    estruturas_bt: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    raw_response: Mapped[str] = mapped_column(Text, nullable=False)

    # Qual client fez essa consulta: 'userbot' (bot DPL) | 'userbot_consulta_api' (API)
    origem_client: Mapped[str] = mapped_column(String(30), default="userbot", nullable=False)

    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Poste code={self.code}>"


# ============================================================================
# EQUIPAMENTOS — 1 linha por código, dado estruturado do @ReincidenciasBot
# ============================================================================
class Equipamento(Base):
    """Dados estruturados de um equipamento/instalação (upsert por `code`)."""
    __tablename__ = "equipamentos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    instalacao: Mapped[str] = mapped_column(String(50), nullable=False)
    tipo: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    poste_referencia: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    potencia: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tensao_primaria: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tensao_secundaria: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fase: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Total agregado do equipamento — NÃO é o dado que o CHI usa (ver Componente.clientes)
    clientes_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    situacao: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    perimetro: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    alimentador: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    raw_response: Mapped[str] = mapped_column(Text, nullable=False)

    origem_client: Mapped[str] = mapped_column(String(30), default="userbot", nullable=False)

    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    componentes: Mapped[list["Componente"]] = relationship(
        back_populates="equipamento", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_equipamentos_instalacao", "instalacao"),
    )

    def __repr__(self) -> str:
        return f"<Equipamento code={self.code} tipo={self.tipo}>"


# ============================================================================
# COMPONENTES — chaves a montante de um equipamento (filha, 1:N)
# ============================================================================
class Componente(Base):
    """
    Uma chave a montante (FU/CF/RG/DJ/SE) de um equipamento.
    Substituída por completo (delete+insert) a cada nova consulta do pai —
    nunca acumula duplicata entre atualizações.
    """
    __tablename__ = "componentes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    equipamento_id: Mapped[str] = mapped_column(
        ForeignKey("equipamentos.id", ondelete="CASCADE"), nullable=False
    )

    tipo: Mapped[str] = mapped_column(String(10), nullable=False)  # FU | CF | RG | DJ | SE
    componente_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    elo: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    clientes: Mapped[int] = mapped_column(Integer, nullable=False)  # ⭐ dado que o CHI precisa
    trafos: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    ordem: Mapped[int] = mapped_column(Integer, nullable=False)  # preserva ordem original da tabela

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    equipamento: Mapped["Equipamento"] = relationship(back_populates="componentes")

    __table_args__ = (
        UniqueConstraint("equipamento_id", "componente_code", name="uq_componente_equipamento_code"),
    )

    def __repr__(self) -> str:
        return f"<Componente {self.tipo} code={self.componente_code} clientes={self.clientes}>"
