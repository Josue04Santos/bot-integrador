"""
Gerenciador de conexão assíncrona — backend-agnostic (SQLite ↔ Postgres).
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Gerenciador singleton de conexões — funciona em SQLite e Postgres."""

    _instance: Optional["DatabaseManager"] = None
    _engine: Optional[AsyncEngine] = None
    _session_factory: Optional[async_sessionmaker] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        """Inicializa engine e session factory."""
        if self._engine is not None:
            logger.warning("Database já inicializado")
            return

        # Configuração específica por backend
        if settings.is_sqlite:
            # SQLite: sem pool size (single-file), connect_args específicos
            self._engine = create_async_engine(
                settings.database_url,
                echo=settings.app_debug,
                future=True,
                connect_args={"check_same_thread": False},
            )
            logger.info("Database (SQLite) inicializado", path=str(settings.sqlite_path))
        else:
            # Postgres: pool completo
            self._engine = create_async_engine(
                settings.database_url,
                echo=settings.app_debug,
                future=True,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
            logger.info(
                "Database (Postgres) inicializado",
                host=settings.postgres_host,
                database=settings.postgres_db,
            )

        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    async def close(self) -> None:
        """Fecha todas as conexões."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database desconectado")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Context manager para sessões.
        
        Uso:
            async with db.session() as session:
                result = await session.execute(query)
        """
        if self._session_factory is None:
            raise RuntimeError("Database não inicializado. Chame initialize() primeiro.")

        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("Erro na transação", error=str(e))
            raise
        finally:
            await session.close()

    @property
    def engine(self) -> Optional[AsyncEngine]:
        return self._engine

    @property
    def is_initialized(self) -> bool:
        return self._engine is not None


# Instância global
db = DatabaseManager()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency para FastAPI."""
    async with db.session() as session:
        yield session
