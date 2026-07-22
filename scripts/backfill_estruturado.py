"""
Backfill único — popula postes/equipamentos/componentes a partir do
code_cache já existente (raw_response salvo, nunca antes estruturado).

Uso:
    python -m scripts.backfill_estruturado           # roda de verdade
    python -m scripts.backfill_estruturado --dry-run # só mostra o que faria
"""
import argparse
import asyncio

from sqlalchemy import select

from src.database.connection import db
from src.database.models import CodeCache
from src.services import persistencia_estruturada
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def main(dry_run: bool = False) -> int:
    await db.initialize()

    async with db.session() as session:
        rows = (await session.execute(select(CodeCache))).scalars().all()

    print(f"code_cache: {len(rows)} registros encontrados")

    ok, nao_encontrado, erro = 0, 0, 0

    for row in rows:
        if dry_run:
            print(f"  [dry-run] {row.query_type:10s} {row.code}")
            continue

        try:
            async with db.session() as session:
                resultado = await persistencia_estruturada.salvar(
                    session,
                    code=row.code,
                    query_type=row.query_type,
                    raw=row.raw_response,
                    origem_client="backfill",
                )
            if resultado is not None:
                ok += 1
            else:
                nao_encontrado += 1
        except Exception:
            erro += 1
            logger.exception("Falha no backfill", code=row.code, query_type=row.query_type)

    print()
    print(f"✅ estruturados: {ok}")
    print(f"⚠️  não encontrado/inválido (não persistido): {nao_encontrado}")
    print(f"❌ erro: {erro}")

    await db.close()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill das tabelas estruturadas a partir do code_cache")
    parser.add_argument("--dry-run", action="store_true", help="Só lista, não grava nada")
    args = parser.parse_args()
    exit_code = asyncio.run(main(dry_run=args.dry_run))
