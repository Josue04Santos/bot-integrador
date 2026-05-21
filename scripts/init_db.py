"""
Bootstrap inicial do banco — cria tabelas e semeia whitelist.
Compatível SQLite e PostgreSQL.

Uso:
    python -m scripts.init_db                # Idempotente
    python -m scripts.init_db --force        # Drop + recreate (⚠️ destrutivo)
    python -m scripts.init_db --no-seed      # Só DDL
    python -m scripts.init_db --check        # Só testa conexão, não cria nada
"""
import argparse
import asyncio
import sys
from datetime import datetime, timezone

from sqlalchemy import select, text

from src.config import settings
from src.database import (
    db,
    Base,
    AuthorizedUser,
    AgentRun,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


WHITELIST_SEED = [
    {
        "tg_id": 5934357886,
        "username": "josuesantos",
        "full_name": "Josué Santos",
        "role": "admin",
        "notes": "Owner do projeto (seed inicial)",
    },
]


# ============================================================================
# DIAGNÓSTICO DE CONEXÃO (novo — específico pra Postgres)
# ============================================================================
async def check_connection() -> dict:
    """
    Testa a conexão e retorna informações úteis sobre o servidor.
    Funciona tanto em SQLite quanto Postgres.
    """
    info = {"backend": settings.database_backend, "connected": False}

    async with db.engine.connect() as conn:
        if settings.is_postgres:
            # Postgres: pega versão, database atual, usuário, encoding
            version = await conn.scalar(text("SELECT version()"))
            current_db = await conn.scalar(text("SELECT current_database()"))
            current_user = await conn.scalar(text("SELECT current_user"))
            encoding = await conn.scalar(text("SHOW server_encoding"))
            
            info.update({
                "connected": True,
                "version": version.split(",")[0] if version else "?",
                "database": current_db,
                "user": current_user,
                "encoding": encoding,
            })
        else:
            # SQLite
            version = await conn.scalar(text("SELECT sqlite_version()"))
            info.update({
                "connected": True,
                "version": f"SQLite {version}",
                "database": str(settings.sqlite_path),
            })

    return info


async def list_existing_tables() -> list[str]:
    """Lista as tabelas que já existem no banco (pra detectar bootstrap parcial)."""
    async with db.engine.connect() as conn:
        if settings.is_postgres:
            result = await conn.execute(text("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' 
                ORDER BY tablename
            """))
        else:
            result = await conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """))
        return [row[0] for row in result.fetchall()]


# ============================================================================
# DDL
# ============================================================================
async def drop_all_tables() -> None:
    logger.warning("Removendo todas as tabelas (DROP CASCADE)...")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.info("✅ Tabelas removidas")


async def create_all_tables() -> None:
    logger.info("Criando tabelas (idempotente)...")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Tabelas criadas/verificadas")


# ============================================================================
# SEED
# ============================================================================
async def seed_whitelist() -> tuple[int, int]:
    created, skipped = 0, 0

    async with db.session() as session:
        for user_data in WHITELIST_SEED:
            tg_id = user_data["tg_id"]
            existing = await session.scalar(
                select(AuthorizedUser).where(AuthorizedUser.tg_id == tg_id)
            )

            if existing:
                logger.info("Usuário já existe", tg_id=tg_id, full_name=existing.full_name)
                skipped += 1
                continue

            session.add(AuthorizedUser(**user_data))
            created += 1
            logger.info("✅ Usuário criado", tg_id=tg_id, role=user_data["role"])

    return created, skipped


async def register_bootstrap_run() -> None:
    async with db.session() as session:
        run = AgentRun(
            agent_type="bootstrap",
            status="stopped",
            stopped_at=datetime.now(timezone.utc),
            meta={
                "action": "init_db",
                "backend": settings.database_backend,
                "tables": sorted(Base.metadata.tables.keys()),
            },
        )
        session.add(run)
    logger.info("✅ Bootstrap registrado em agent_runs")


# ============================================================================
# MAIN
# ============================================================================
async def main(force: bool = False, no_seed: bool = False, check_only: bool = False) -> int:
    print()
    print("=" * 72)
    print(" 🚀 BOT INTEGRADOR — Bootstrap do Banco de Dados")
    print("=" * 72)
    print(f"  Backend:  {settings.database_backend.upper()}")
    
    # Não printa a URL completa em Postgres (tem senha)
    if settings.is_postgres:
        print(f"  Host:     {settings.postgres_host}:{settings.postgres_port}")
        print(f"  Database: {settings.postgres_db}")
        print(f"  User:     {settings.postgres_user}")
    else:
        print(f"  Arquivo:  {settings.sqlite_path}")
    
    print(f"  Modo:     {'CHECK (só testa)' if check_only else ('FORCE (drop+create)' if force else 'IDEMPOTENTE')}")
    print(f"  Seed:     {'NÃO' if (no_seed or check_only) else 'SIM (whitelist)'}")
    print("=" * 72)
    print()

    if force and not check_only:
        confirm = input("⚠️  --force vai APAGAR todos os dados. Confirma? [yes/N]: ")
        if confirm.lower() != "yes":
            print("❌ Cancelado pelo usuário")
            return 1

    try:
        # 1) Conecta
        await db.initialize()

        # 2) Testa conexão (sempre)
        print("🔌 Testando conexão...")
        info = await check_connection()
        print(f"   ✅ Conectado!")
        if "version" in info:
            print(f"      {info['version']}")
        if "user" in info:
            print(f"      User:     {info['user']}")
            print(f"      Database: {info['database']}")
            print(f"      Encoding: {info.get('encoding', '?')}")
        print()

        # 3) Lista tabelas existentes (antes de qualquer DDL)
        existing = await list_existing_tables()
        print(f"📋 Tabelas existentes: {len(existing)}")
        if existing:
            for t in existing:
                marker = "✓" if t in Base.metadata.tables else "?"
                print(f"   {marker} {t}")
        else:
            print("   (banco vazio)")
        print()

        if check_only:
            print("=" * 72)
            print(" ✅ CHECK concluído — conexão OK, nenhuma alteração feita")
            print("=" * 72)
            return 0

        # 4) Drop (opcional)
        if force:
            await drop_all_tables()

        # 5) Create
        await create_all_tables()

        # 6) Confirma tabelas criadas
        after = await list_existing_tables()
        new_tables = set(after) - set(existing) if not force else set(after)
        if new_tables:
            print(f"✨ Tabelas criadas nesta execução: {len(new_tables)}")
            for t in sorted(new_tables):
                print(f"   + {t}")
            print()

        # 7) Seed
        if not no_seed:
            created, skipped = await seed_whitelist()
            print(f"📊 Whitelist: {created} criado(s), {skipped} já existia(m)")
            print()

        # 8) Auditoria
        await register_bootstrap_run()

        print("=" * 72)
        print(" ✅ Bootstrap concluído com sucesso!")
        print("=" * 72)
        print()
        print("Próximos passos:")
        print("  • Status do banco:  python -m scripts.db_status")
        print("  • Iniciar bots:     python -m src.main")
        print()
        return 0

    except Exception as e:
        logger.error("Erro no bootstrap", error=str(e), exc_info=True)
        print(f"\n❌ Erro: {type(e).__name__}: {e}")
        print()
        print("Dicas de troubleshooting:")
        print("  • Postgres está rodando?  systemctl status postgresql  (ou docker ps)")
        print("  • Banco existe?           psql -l")
        print("  • Credenciais corretas?   confira o .env")
        print("  • Porta acessível?        nc -zv HOST PORT")
        return 1
    finally:
        await db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootstrap do banco do Bot Integrador")
    parser.add_argument("--force", action="store_true", help="Drop tudo antes de criar")
    parser.add_argument("--no-seed", action="store_true", help="Não semear whitelist")
    parser.add_argument("--check", action="store_true", help="Só testa conexão (sem alterar nada)")
    args = parser.parse_args()

    exit_code = asyncio.run(main(force=args.force, no_seed=args.no_seed, check_only=args.check))
    sys.exit(exit_code)
