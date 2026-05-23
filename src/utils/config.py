"""
Configurações centralizadas — backend-agnostic (SQLite ↔ Postgres).
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações globais do Bot Integrador."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Telegram Bot (BotFather) ---
    telegram_bot_token: str
    telegram_webhook_url: str = ""
    telegram_webhook_secret: str = ""
    webhook_enabled: bool = False

    # --- Telegram Userbot (MTProto) ---
    telegram_api_id: int
    telegram_api_hash: str
    telegram_phone: str

    # --- Bot de terceiros (alvo das consultas) ---
    bot_terceiro_username: str = "ReincidenciasBot"
    bot_terceiro_timeout: int = 30

    # --- Grupo/Canal monitorado (opcional) ---
    telegram_source_chat_id: int = 0

    # --- DATABASE (backend-agnostic) ---
    database_backend: Literal["sqlite", "postgres"] = "sqlite"
    sqlite_path: Path = Path("./data/bot_integrador.db")

    # Postgres (usado quando database_backend=postgres)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "bot_integrador"
    postgres_user: str = "bot_user"
    postgres_password: str = ""

    # --- Aplicação ---
    app_env: str = "development"
    app_debug: bool = True
    app_log_level: str = "INFO"

    # --- API ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str = "chave-padrao-dev"

    # --- Paths ---
    sessions_path: Path = Path("./sessions")
    logs_path: Path = Path("./logs")
    output_path: Path = Path("./output")

    # --- Userbot Session ---
    session_name: str = "userbot_session"

    # --- Consultas / Rate Limiting ---
    delay_between_queries: float = 3.0
    rate_limit_delay: float = 2.0
    consulta_timeout: float = 30.0
    max_consultas_batch: int = 50

    # --- Administração ---
    super_admin_ids: Union[str, list[int]] = ""

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("sessions_path", "logs_path", "output_path", mode="after")
    @classmethod
    def ensure_directory(cls, v: Path) -> Path:
        """Garante que diretórios existam."""
        v.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator("sqlite_path", mode="after")
    @classmethod
    def ensure_sqlite_parent(cls, v: Path) -> Path:
        """Garante que pasta do SQLite exista."""
        v.parent.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator("super_admin_ids", mode="before")
    @classmethod
    def parse_super_admin_ids(cls, v) -> list[int]:
        """Converte string CSV em lista de inteiros."""
        if isinstance(v, list):
            return v
        if isinstance(v, (str, int)):
            if isinstance(v, int):
                return [v]
            if not v.strip():
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return []

    # ------------------------------------------------------------------
    # Properties derivadas
    # ------------------------------------------------------------------
    @property
    def database_url(self) -> str:
        """URL de conexão assíncrona — alterna entre SQLite e Postgres."""
        if self.database_backend == "sqlite":
            return f"sqlite+aiosqlite:///{self.sqlite_path}"
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_sqlite(self) -> bool:
        return self.database_backend == "sqlite"

    @property
    def is_postgres(self) -> bool:
        return self.database_backend == "postgres"

    @property
    def database_url_safe(self) -> str:
        """URL com senha mascarada — para logs."""
        url = self.database_url
        if self.is_postgres and self.postgres_password:
            url = url.replace(self.postgres_password, "***")
        return url

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Retorna instância cacheada das configurações."""
    return Settings()
