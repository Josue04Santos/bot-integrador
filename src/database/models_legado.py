"""
Tabelas que existem no Postgres de produção mas nunca foram declaradas em
`models.py` — criadas ad hoc (DDL manual), fora do fluxo SQLAlchemy/Alembic.

Declaradas aqui só para o Alembic parar de vê-las como "removidas" (o que
geraria DROP TABLE na migration baseline). Não usar para lógica nova —
são legado.
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models import Base


class TelethonSession(Base):
    """
    Sessão Telethon (StringSession) do userbot, persistida no Postgres.
    Gerenciada via DDL manual em `src/userbot/client.py` (`_ensure_table`),
    não por este model — mantido aqui só pra registro no Alembic.
    """
    __tablename__ = "telethon_sessions"

    session_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    session_data: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    __table_args__ = (
        Index("idx_telethon_sessions_updated", "updated_at"),
    )


class UsuarioLegado(Base):
    """
    Tabela legada, anterior a `authorized_users`. Sem uso confirmado no
    código atual — mantida só pra não ser derrubada por engano via Alembic.
    """
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    authorized: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    __table_args__ = (
        Index("idx_usuarios_telegram_id", "telegram_id"),
    )
