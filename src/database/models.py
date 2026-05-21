"""
Modelos SQLAlchemy do Bot Integrador — domínio EQTL/DPL.

Tabelas:
    - authorized_users     → whitelist de usuários do bot DPL
    - query_batches        → lotes de consulta enviados por um usuário
    - network_queries      → cada consulta individual (poste/instalação)
    - meters               → medidores/clientes vinculados a uma instalação
    - kml_exports          → arquivos KML gerados
    - agent_runs           → telemetria de execução do userbot

Portabilidade: 100% compatível SQLite ↔ PostgreSQL.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    BigInteger,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.database.types import uuid7


def utcnow() -> datetime:
    """Timestamp UTC consistente entre bancos."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Classe base para todos os modelos."""
    pass


# ============================================================================
# 1) AUTHORIZED USERS — Whitelist do bot DPL
# ============================================================================
class AuthorizedUser(Base):
    """Usuários autorizados a usar o bot DPL."""
    __tablename__ = "authorized_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)  # admin | user | readonly
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relacionamentos
    batches: Mapped[list["QueryBatch"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AuthorizedUser tg_id={self.tg_id} role={self.role} active={self.active}>"


# ============================================================================
# 2) QUERY BATCH — Lote de consultas (1 comando do usuário = 1 batch)
# ============================================================================
class QueryBatch(Base):
    """
    Lote de consultas disparado por um usuário.
    Ex.: usuário envia '/lote 123,456,789' → cria 1 batch com 3 queries.
    """
    __tablename__ = "query_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    user_id: Mapped[str] = mapped_column(ForeignKey("authorized_users.id", ondelete="CASCADE"), nullable=False)

    # Origem do lote
    source: Mapped[str] = mapped_column(String(20), default="bot", nullable=False)  # bot | api | upload
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)  # input bruto do usuário (auditoria)

    # Status e contagens
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  
    # pending | running | completed | failed | cancelled
    
    total_codes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    timeout_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timeline
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Erro global (se houve)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relacionamentos
    user: Mapped["AuthorizedUser"] = relationship(back_populates="batches")
    queries: Mapped[list["NetworkQuery"]] = relationship(back_populates="batch", cascade="all, delete-orphan")
    kml_export: Mapped[Optional["KmlExport"]] = relationship(back_populates="batch", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_batches_user_status", "user_id", "status"),
        Index("ix_batches_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<QueryBatch id={self.id[:8]} status={self.status} {self.success_count}/{self.total_codes}>"


# ============================================================================
# 3) NETWORK QUERY — Consulta individual (1 código consultado no ReincidenciasBot)
# ============================================================================
class NetworkQuery(Base):
    """
    Uma consulta individual ao @ReincidenciasBot.
    Representa 1 código (poste ou instalação) e sua resposta.
    """
    __tablename__ = "network_queries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    batch_id: Mapped[str] = mapped_column(ForeignKey("query_batches.id", ondelete="CASCADE"), nullable=False)

    # Entrada
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    query_type: Mapped[str] = mapped_column(String(20), default="poste", nullable=False)  
    # poste | instalacao | desconhecido

    # Status
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # pending | sent | received | parsed | timeout | error

    # Resposta bruta (sempre salvamos pra reprocessar parser se mudar)
    raw_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Dados parseados (JSON portável)
    parsed_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Ex: {"alimentador": "BJU01J3", "perimetro": "RURAL", "potencia": "75 kVA", ...}

    # Coordenadas (extraídas pra facilitar queries geográficas)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Metadados elétricos (denormalizados para queries rápidas)
    alimentador: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    poste: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Timeline (1 linha = 1 consulta = ~5-10s de vida)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    response_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # tempo de resposta

    # Erro (se houve)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relacionamentos
    batch: Mapped["QueryBatch"] = relationship(back_populates="queries")
    meters: Mapped[list["Meter"]] = relationship(back_populates="query", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_queries_batch_status", "batch_id", "status"),
        Index("ix_queries_code", "code"),
        Index("ix_queries_alimentador", "alimentador"),
        Index("ix_queries_coords", "latitude", "longitude"),
    )

    def __repr__(self) -> str:
        return f"<NetworkQuery code={self.code} type={self.query_type} status={self.status}>"


# ============================================================================
# 4) METER — Medidor/cliente (filhos de uma Instalação)
# ============================================================================
class Meter(Base):
    """
    Medidor/cliente vinculado a uma instalação (transformador).
    Uma instalação pode ter N medidores (chaves a montante / clientes alimentados).
    """
    __tablename__ = "meters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    query_id: Mapped[str] = mapped_column(ForeignKey("network_queries.id", ondelete="CASCADE"), nullable=False)

    # Dados do medidor / chave a montante
    componente: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # FU, CF, RG, DJ, SE
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    elo: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # 6K, 10K, LAM, ...
    clientes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    trafos: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relacionamentos
    query: Mapped["NetworkQuery"] = relationship(back_populates="meters")

    __table_args__ = (
        Index("ix_meters_query", "query_id"),
    )

    def __repr__(self) -> str:
        return f"<Meter {self.componente} code={self.code} clientes={self.clientes}>"


# ============================================================================
# 5) KML EXPORT — Arquivo .kml gerado a partir de um batch
# ============================================================================
class KmlExport(Base):
    """Arquivo KML gerado a partir de um QueryBatch."""
    __tablename__ = "kml_exports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    batch_id: Mapped[str] = mapped_column(ForeignKey("query_batches.id", ondelete="CASCADE"), unique=True, nullable=False)

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    placemark_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Telegram message_id (se já foi enviado)
    telegram_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    sent_to_user: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relacionamentos
    batch: Mapped["QueryBatch"] = relationship(back_populates="kml_export")

    def __repr__(self) -> str:
        return f"<KmlExport {self.filename} placemarks={self.placemark_count}>"


# ============================================================================
# 6) AGENT RUN — Telemetria de execução do userbot (auditoria)
# ============================================================================
class AgentRun(Base):
    """
    Telemetria de execução do userbot.
    1 registro por sessão de userbot conectado (start → stop).
    Útil para detectar crashes, reconexões, tempo de uptime.
    """
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    agent_type: Mapped[str] = mapped_column(String(20), default="userbot", nullable=False)
    # userbot | dpl_bot | api

    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    # running | stopped | crashed

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Metadados (versão do app, hostname, etc)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AgentRun {self.agent_type} status={self.status} started={self.started_at}>"
