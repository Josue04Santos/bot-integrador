"""
Cliente OSRM — busca rota rodoviária REAL entre pontos.

OSRM público (router.project-osrm.org) é gratuito, sem chave.
Limites: ~1 req/s, "fair use". Pra produção pesada, hospede o seu.

Documentação: http://project-osrm.org/docs/v5.23.0/api/
"""
import asyncio
from dataclasses import dataclass
from typing import List, Optional, Tuple

import httpx

from src.utils.logger import get_logger

logger = get_logger(__name__)

OSRM_BASE_URL = "https://router.project-osrm.org"
OSRM_TIMEOUT = 20.0
OSRM_MAX_RETRIES = 2
# OSRM público limita URL ~8KB → ~500 coords. Pra rotas grandes, dividimos.
OSRM_MAX_COORDS_PER_REQUEST = 100


@dataclass
class OSRMRoute:
    """Resultado de uma rota rodoviária OSRM."""
    geometry: List[Tuple[float, float]]  # [(lat, lon), ...] da polyline real
    distance_m: float                    # distância por estradas (metros)
    duration_s: float                    # tempo estimado (segundos)


async def fetch_route(
    coords: List[Tuple[float, float]],
    profile: str = "driving",
) -> Optional[OSRMRoute]:
    """
    Busca rota rodoviária real passando por TODOS os pontos na ordem dada.

    Args:
        coords: lista de (lat, lon) na ordem desejada de visita.
        profile: 'driving' (carro/moto), 'cycling' (bike), 'foot' (pé).
                 OBS: OSRM público só serve 'driving' garantido.

    Returns:
        OSRMRoute com geometria detalhada, ou None se falhar.
    """
    if len(coords) < 2:
        logger.debug("OSRM: menos de 2 pontos, nada a rotear")
        return None

    # Se >100 pontos, dividir em chunks e mesclar
    if len(coords) > OSRM_MAX_COORDS_PER_REQUEST:
        return await _fetch_route_chunked(coords, profile)

    return await _fetch_single(coords, profile)


async def _fetch_single(
    coords: List[Tuple[float, float]],
    profile: str,
) -> Optional[OSRMRoute]:
    """Busca rota em chamada única (até ~100 pontos)."""
    # OSRM espera "lon,lat;lon,lat;..." (ATENÇÃO: ordem invertida!)
    coords_str = ";".join(f"{lon},{lat}" for lat, lon in coords)
    url = f"{OSRM_BASE_URL}/route/v1/{profile}/{coords_str}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
        "annotations": "false",
    }

    async with httpx.AsyncClient(timeout=OSRM_TIMEOUT) as client:
        for attempt in range(OSRM_MAX_RETRIES + 1):
            try:
                resp = await client.get(url, params=params)

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == "Ok" and data.get("routes"):
                        route = data["routes"][0]
                        geom_lonlat = route["geometry"]["coordinates"]
                        geom_latlon = [(lat, lon) for lon, lat in geom_lonlat]
                        return OSRMRoute(
                            geometry=geom_latlon,
                            distance_m=float(route["distance"]),
                            duration_s=float(route["duration"]),
                        )
                    logger.warning(
                        "OSRM código não-Ok",
                        code=data.get("code"),
                        msg=data.get("message", "")[:200],
                    )
                    return None

                if resp.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"OSRM rate-limited, aguardando {wait}s")
                    await asyncio.sleep(wait)
                    continue

                logger.warning(
                    f"OSRM HTTP {resp.status_code}",
                    body=resp.text[:200],
                )
                return None

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt < OSRM_MAX_RETRIES:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                logger.warning("OSRM timeout/conexão", error=str(e))
                return None
            except Exception as e:
                logger.exception("OSRM erro inesperado", error=str(e))
                return None

    return None


async def _fetch_route_chunked(
    coords: List[Tuple[float, float]],
    profile: str,
) -> Optional[OSRMRoute]:
    """Para rotas muito grandes: divide, requisita em pedaços, mescla geometria."""
    logger.info(f"OSRM chunked: {len(coords)} pontos em chunks de {OSRM_MAX_COORDS_PER_REQUEST}")

    merged_geom: List[Tuple[float, float]] = []
    total_dist = 0.0
    total_dur = 0.0
    step = OSRM_MAX_COORDS_PER_REQUEST - 1  # overlap de 1 ponto

    i = 0
    while i < len(coords) - 1:
        chunk = coords[i:i + OSRM_MAX_COORDS_PER_REQUEST]
        if len(chunk) < 2:
            break
        result = await _fetch_single(chunk, profile)
        if not result:
            return None
        # Evita duplicar o ponto de junção
        if merged_geom and result.geometry:
            merged_geom.extend(result.geometry[1:])
        else:
            merged_geom.extend(result.geometry)
        total_dist += result.distance_m
        total_dur += result.duration_s
        i += step
        # respeita o rate-limit do servidor público
        await asyncio.sleep(1.1)

    if not merged_geom:
        return None
    return OSRMRoute(geometry=merged_geom, distance_m=total_dist, duration_s=total_dur)


__all__ = ["fetch_route", "OSRMRoute"]
