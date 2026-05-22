"""
Módulo de exportação: KML + CSV + TXT de inválidos.

Uso típico:
    from src.exporters import generate_bundle
    bundle = await generate_bundle(batch_id)
    # bundle.kml_bytes, bundle.csv_bytes, bundle.invalidos_txt, bundle.filename_base
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from src.database.connection import db
from src.database.models import NetworkQuery, QueryBatch

from .csv_builder import build_csv
from .kml_builder import build_invalidos_txt, build_kml
from .parser import PosteData, parse_poste_response


@dataclass
class ExportBundle:
    batch_id: str
    filename_base: str          # ex: "postes_2026-05-21_019e4d26"
    kml_bytes: bytes
    csv_bytes: bytes
    invalidos_txt: str          # vazio se não houver inválidos
    total: int
    com_coords: int
    sem_coords: int


async def generate_bundle(batch_id: str) -> ExportBundle | None:
    """
    Gera o pacote completo de exportação para um batch.
    Retorna None se o batch não existir.
    """
    async with db.session() as session:
        batch = await session.get(QueryBatch, batch_id)
        if not batch:
            return None

        result = await session.execute(
            select(NetworkQuery).where(NetworkQuery.batch_id == batch_id)
        )
        queries = result.scalars().all()

    # Parse de todas as respostas
    todos: list[PosteData] = []
    for q in queries:
        p = parse_poste_response(q.code, q.raw_response)
        if q.status != "received" and not p.parse_error:
            p.parse_error = f"status={q.status}"
        todos.append(p)

    com_coords = [p for p in todos if p.has_coords]
    sem_coords = [p for p in todos if not p.has_coords]

    # Nome do arquivo
    data_str = (batch.created_at or datetime.utcnow()).strftime("%Y-%m-%d")
    short_id = batch_id.replace("-", "")[:8]
    filename_base = f"postes_{data_str}_{short_id}"

    return ExportBundle(
        batch_id=batch_id,
        filename_base=filename_base,
        kml_bytes=build_kml(com_coords, batch_id, sem_coords).encode("utf-8"),
        csv_bytes=build_csv(todos),
        invalidos_txt=build_invalidos_txt(sem_coords),
        total=len(todos),
        com_coords=len(com_coords),
        sem_coords=len(sem_coords),
    )


__all__ = ["ExportBundle", "generate_bundle", "parse_poste_response", "PosteData"]
