"""
Migração: network_queries → code_cache
Popula code_cache com o resultado mais recente de cada código único.
Execução: python -m scripts.migrate_cache
"""
import asyncio
from sqlalchemy import text
from src.database.connection import db
from src.database.types import uuid7
from src.utils.logger import setup_logging


async def main() -> None:
    setup_logging()
    await db.initialize()

    # Busca o registro mais recente de cada (code, query_type) com resposta válida
    async with db.session() as session:
        result = await session.execute(text("""
            SELECT DISTINCT ON (code, query_type)
                code,
                query_type,
                raw_response,
                parsed_data,
                latitude,
                longitude,
                alimentador,
                received_at
            FROM network_queries
            WHERE status = 'received'
              AND raw_response IS NOT NULL
            ORDER BY code, query_type, received_at DESC
        """))
        rows = result.fetchall()

    print(f"\nEncontrados {len(rows)} registros únicos para migrar...\n")

    inserted = 0
    updated = 0

    for row in rows:
        code, query_type, raw_response, parsed_data, lat, lng, alim, received_at = row

        async with db.session() as session:
            existing = await session.execute(text(
                "SELECT id FROM code_cache WHERE code = :c AND query_type = :t"
            ), {"c": code, "t": query_type})
            found = existing.fetchone()

            if found:
                await session.execute(text("""
                    UPDATE code_cache SET
                        raw_response    = :raw,
                        parsed_data     = :parsed,
                        latitude        = :lat,
                        longitude       = :lng,
                        alimentador     = :alim,
                        last_fetched_at = :ts
                    WHERE code = :c AND query_type = :t
                """), {
                    "raw": raw_response, "parsed": parsed_data,
                    "lat": lat, "lng": lng, "alim": alim,
                    "ts": received_at, "c": code, "t": query_type,
                })
                updated += 1
            else:
                await session.execute(text("""
                    INSERT INTO code_cache
                        (id, code, query_type, raw_response, parsed_data,
                         latitude, longitude, alimentador,
                         fetch_count, first_fetched_at, last_fetched_at)
                    VALUES
                        (:id, :c, :t, :raw, :parsed,
                         :lat, :lng, :alim,
                         1, :ts, :ts)
                """), {
                    "id": uuid7(), "raw": raw_response, "parsed": parsed_data,
                    "lat": lat, "lng": lng, "alim": alim,
                    "ts": received_at, "c": code, "t": query_type,
                })
                inserted += 1

        # Progresso a cada 50
        done = inserted + updated
        if done % 50 == 0:
            print(f"  ... {done}/{len(rows)}")

    # Resultado final
    async with db.session() as session:
        r = await session.execute(text(
            "SELECT query_type, COUNT(*) FROM code_cache GROUP BY query_type"
        ))
        totais = r.fetchall()

    print(f"\n✅ Migração concluída!")
    print(f"   Inseridos  : {inserted}")
    print(f"   Atualizados: {updated}")
    print(f"\ncode_cache agora:")
    for query_type, count in totais:
        print(f"   {query_type:12s}: {count} registros únicos")

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
