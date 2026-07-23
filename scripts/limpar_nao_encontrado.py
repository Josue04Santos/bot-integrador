"""
Escape hatch — remove um código da lista de "não encontrados", forçando
a próxima consulta a reconsultar o bot terceiro ao vivo (em vez de esperar
o TTL de 30 dias vencer).

Uso:
    python -m scripts.limpar_nao_encontrado 0053910 --tipo poste
    python -m scripts.limpar_nao_encontrado 0053910 --tipo equipamento
    python -m scripts.limpar_nao_encontrado --listar          # lista tudo
"""
import argparse
import asyncio

from sqlalchemy import delete, select

from src.database.connection import db
from src.database.models_nao_encontrado import CodigoNaoEncontrado

_TIPO_PARA_QUERY_TYPE = {"poste": "poste", "equipamento": "instalacao"}


async def listar() -> int:
    await db.initialize()
    async with db.session() as session:
        rows = (await session.execute(select(CodigoNaoEncontrado))).scalars().all()
    if not rows:
        print("Lista de não encontrados está vazia.")
    for r in rows:
        print(f"  {r.code:15s} {r.query_type:12s} confirmado em {r.checked_at}")
    print(f"\nTotal: {len(rows)}")
    await db.close()
    return 0


async def remover(code: str, tipo: str) -> int:
    query_type = _TIPO_PARA_QUERY_TYPE[tipo]
    await db.initialize()
    async with db.session() as session:
        result = await session.execute(
            delete(CodigoNaoEncontrado).where(
                CodigoNaoEncontrado.code == code,
                CodigoNaoEncontrado.query_type == query_type,
            )
        )
    await db.close()

    if result.rowcount:
        print(f"✅ Removido: {code} ({tipo}) — próxima consulta vai ao vivo de novo.")
    else:
        print(f"⚠️  {code} ({tipo}) não estava na lista de não encontrados.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove um código da lista de não encontrados")
    parser.add_argument("code", nargs="?", help="Código a remover")
    parser.add_argument("--tipo", choices=["poste", "equipamento"], help="Tipo do código")
    parser.add_argument("--listar", action="store_true", help="Lista todos os códigos não encontrados")
    args = parser.parse_args()

    if args.listar:
        exit_code = asyncio.run(listar())
    elif args.code and args.tipo:
        exit_code = asyncio.run(remover(args.code, args.tipo))
    else:
        parser.error("informe 'code --tipo poste|equipamento' ou use --listar")
        exit_code = 1
