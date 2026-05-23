"""
Módulo de exportação: KML otimizado (µ9) + GPX + CSV + TXT.

Pipeline:
  1. Parse das respostas (postes E equipamentos)
  2. TSP (OR-Tools) → ordem ótima (só postes com coords)
  3. OSRM → geometria rodoviária real
  4. KML + GPX + CSV (2 arquivos: postes.csv + equipamentos.csv)
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from src.database.connection import db
from src.database.models import NetworkQuery, QueryBatch
from src.services.osrm_client import fetch_route as osrm_fetch_route
from src.services.route_optimizer import RouteOptimizer
from src.utils.logger import get_logger

from .adapter import postes_to_routepoints
from .csv_builder import build_csv as build_csv_postes
from .csv_equipamentos import build_csv as build_csv_equipamentos
from .gpx_builder import build_gpx
from .gpx_equipamentos import build_gpx_equipamentos
from .kml_builder import build_invalidos_txt, build_kml
from .parser import PosteData, parse_poste_response
from .parser_equipamento import EquipamentoData, parse_equipamento_response

logger = get_logger(__name__)


@dataclass
class OptimizationStats:
    """Estatísticas da otimização."""
    natural_km: float
    otimizada_km: float
    economia_pct: float
    n_paradas: int
    tempo_ms: float
    # OSRM (rota rodoviária real) — opcionais
    rodoviaria_km: float | None = None
    tempo_viagem_min: float | None = None


@dataclass
class ExportBundle:
    batch_id: str
    filename_base: str
    kml_bytes: bytes
    gpx_bytes: bytes
    gpx_equipamentos_bytes: bytes  # 🆕 equipamentos
    csv_postes_bytes: bytes  # 🆕 separado
    csv_equipamentos_bytes: bytes  # 🆕 novo
    invalidos_txt: str
    total: int
    com_coords: int
    sem_coords: int
    total_postes: int  # 🆕
    total_equipamentos: int  # 🆕
    optimization: OptimizationStats | None = None


async def generate_bundle(batch_id: str) -> ExportBundle | None:
    """Gera o pacote completo de exportação para um batch."""
    async with db.session() as session:
        batch = await session.get(QueryBatch, batch_id)
        if not batch:
            return None

        result = await session.execute(
            select(NetworkQuery).where(NetworkQuery.batch_id == batch_id)
        )
        queries = result.scalars().all()

    # ═══════════════════════════════════════════════════════════
    # 🆕 PARSE RAMIFICADO POR TIPO
    # ═══════════════════════════════════════════════════════════
    postes: list[PosteData] = []
    equipamentos: list[EquipamentoData] = []

    for q in queries:
        if q.query_type == "instalacao":
            e = parse_equipamento_response(q.code, q.raw_response)
            if q.status != "received" and not e.parse_error:
                e.parse_error = f"status={q.status}"
            equipamentos.append(e)
        else:
            p = parse_poste_response(q.code, q.raw_response)
            if q.status != "received" and not p.parse_error:
                p.parse_error = f"status={q.status}"
            postes.append(p)

    # Separa válidos/inválidos (só postes vão pro KML/GPX por enquanto)
    postes_com_coords = [p for p in postes if p.has_coords]
    postes_sem_coords = [p for p in postes if not p.has_coords]
    equipamentos_com_coords = [e for e in equipamentos if e.has_coords]
    equipamentos_sem_coords = [e for e in equipamentos if not e.has_coords]

    total_com_coords = len(postes_com_coords) + len(equipamentos_com_coords)
    total_sem_coords = len(postes_sem_coords) + len(equipamentos_sem_coords)

    # ════════ µ9 — Otimização TSP (só postes) ════════
    optimization: OptimizationStats | None = None
    ordem: list[str] | None = None

    if len(postes_com_coords) >= 2:
        try:
            route_points = postes_to_routepoints(postes_com_coords)
            resultado = RouteOptimizer().optimize(route_points)

            ordem = resultado.ordem
            optimization = OptimizationStats(
                natural_km=resultado.distancia_natural_km,
                otimizada_km=resultado.distancia_otimizada_km,
                economia_pct=resultado.economia_pct,
                n_paradas=len(ordem),
                tempo_ms=resultado.tempo_execucao_ms,
            )
            logger.info(
                "µ9 otimizou rota",
                batch_id=batch_id[:8],
                economia_pct=round(resultado.economia_pct, 1),
                paradas=len(ordem),
                tempo_ms=round(resultado.tempo_execucao_ms, 1),
            )
        except Exception as e:
            logger.warning(
                "µ9 falhou — usando ordem natural",
                batch_id=batch_id[:8],
                error=str(e),
                error_type=type(e).__name__,
            )
            ordem = None

    # ════════ OSRM — Geometria rodoviária real ════════
    route_geometry: list[tuple[float, float]] | None = None

    if ordem and len(postes_com_coords) >= 2:
        by_code = {p.code: p for p in postes_com_coords}
        coords_ordenadas = [
            (by_code[c].lat, by_code[c].lng)
            for c in ordem if c in by_code
        ]
        try:
            osrm_result = await osrm_fetch_route(coords_ordenadas, profile="driving")
            if osrm_result:
                route_geometry = osrm_result.geometry
                if optimization:
                    optimization.rodoviaria_km = osrm_result.distance_m / 1000
                    optimization.tempo_viagem_min = osrm_result.duration_s / 60
                logger.info(
                    "OSRM traçou rota rodoviária",
                    batch_id=batch_id[:8],
                    pontos_geometria=len(route_geometry),
                    distancia_real_km=round(osrm_result.distance_m / 1000, 2),
                    tempo_min=round(osrm_result.duration_s / 60, 1),
                )
            else:
                logger.info(
                    "OSRM não retornou rota — KML/GPX usarão linha reta",
                    batch_id=batch_id[:8],
                )
        except Exception as e:
            logger.warning(
                "OSRM falhou — fallback para linha reta",
                batch_id=batch_id[:8],
                error=str(e),
                error_type=type(e).__name__,
            )

    # Nome do arquivo
    data_str = (batch.created_at or datetime.utcnow()).strftime("%Y-%m-%d")
    short_id = batch_id.replace("-", "")[:8]
    filename_base = f"lote_{data_str}_{short_id}"

    # KML (postes + equipamentos com coords)
    kml_xml = build_kml(
        postes_com_coords,
        batch_id,
        postes_sem_coords,
        ordem=ordem,
        distancia_natural_km=optimization.natural_km if optimization else None,
        distancia_otimizada_km=optimization.otimizada_km if optimization else None,
        economia_pct=optimization.economia_pct if optimization else None,
        route_geometry=route_geometry,
        distancia_rodoviaria_km=optimization.rodoviaria_km if optimization else None,
        tempo_estimado_min=optimization.tempo_viagem_min if optimization else None,
    )

    # GPX postes (com rota otimizada)
    gpx_xml = (
        build_gpx(postes_com_coords, batch_id, ordem=ordem, route_geometry=route_geometry)
        if postes_com_coords else ""
    )

    # 🆕 GPX equipamentos (apenas waypoints)
    gpx_equipamentos_xml = (
        build_gpx_equipamentos(equipamentos_com_coords, batch_id)
        if equipamentos_com_coords else ""
    )

    # 🆕 TXT de inválidos (postes + equipamentos)
    invalidos_txt_parts = []
    if postes_sem_coords:
        invalidos_txt_parts.append(build_invalidos_txt(postes_sem_coords))
    if equipamentos_sem_coords:
        invalidos_txt_parts.append(
            f"\n{'='*60}\nEQUIPAMENTOS SEM COORDENADAS ({len(equipamentos_sem_coords)})\n{'='*60}\n"
            + "\n".join(e.code for e in equipamentos_sem_coords)
        )
    invalidos_txt = "\n".join(invalidos_txt_parts)

    return ExportBundle(
        batch_id=batch_id,
        filename_base=filename_base,
        kml_bytes=kml_xml.encode("utf-8"),
        gpx_bytes=gpx_xml.encode("utf-8") if gpx_xml else b"",
        gpx_equipamentos_bytes=gpx_equipamentos_xml.encode("utf-8") if gpx_equipamentos_xml else b"",
        csv_postes_bytes=build_csv_postes(postes),
        csv_equipamentos_bytes=build_csv_equipamentos(equipamentos),
        invalidos_txt=invalidos_txt,
        total=len(postes) + len(equipamentos),
        com_coords=total_com_coords,
        sem_coords=total_sem_coords,
        total_postes=len(postes),
        total_equipamentos=len(equipamentos),
        optimization=optimization,
    )


__all__ = [
    "ExportBundle",
    "OptimizationStats",
    "generate_bundle",
    "parse_poste_response",
    "parse_equipamento_response",
    "PosteData",
    "EquipamentoData",
]
