"""
db_status.py — Diagnóstico operacional do banco.

Mostra:
- Backend atual (SQLite/Postgres) + URL mascarada
- Contagem de registros em todas as tabelas
- Lista de usuários autorizados
"""
import asyncio
from sqlalchemy import func, select

from src.config import settings
from src.database import (
    db, AuthorizedUser, QueryBatch, NetworkQuery,
    Meter, KmlExport, AgentRun,
)


async def main() -> None:
    print()
    print("=" * 72)
    print(" 📊 BOT INTEGRADOR — Status do Banco")
    print("=" * 72)
    print(f"  Backend:  {settings.database_backend.upper()}")
    print(f"  URL:      {settings.database_url_safe}")
    print("=" * 72)
    print()

    await db.initialize()
    try:
        async with db.session() as session:
            tables = [
                ("authorized_users", AuthorizedUser),
                ("query_batches",    QueryBatch),
                ("network_queries",  NetworkQuery),
                ("meters",           Meter),
                ("kml_exports",      KmlExport),
                ("agent_runs",       AgentRun),
            ]

            print(f"  {'Tabela':<22} {'Registros':>12}")
            print("  " + "-" * 36)
            for name, model in tables:
                count = await session.scalar(
                    select(func.count()).select_from(model)
                )
                print(f"  {name:<22} {count:>12}")
            print()

            users = (await session.execute(
                select(AuthorizedUser).order_by(AuthorizedUser.created_at)
            )).scalars().all()

            if users:
                print("  👥 USUÁRIOS AUTORIZADOS:")
                print(f"     {'tg_id':<14} {'role':<10} {'active':<8} {'nome'}")
                print("     " + "-" * 56)
                for u in users:
                    print(
                        f"     {u.tg_id:<14} {u.role:<10} "
                        f"{str(u.active):<8} {u.full_name or '-'}"
                    )
                print()
            else:
                print("  ℹ️  Nenhum usuário cadastrado ainda.")
                print()

        print("=" * 72)
        print(" ✅ Banco acessível e operacional")
        print("=" * 72)
        print()
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
