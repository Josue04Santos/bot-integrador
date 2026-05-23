"""
Adapter entre PosteData (exporters) e RoutePoint (route_optimizer).

Mantém os dois módulos desacoplados — exporters não sabe da existência
do otimizador, e vice-versa.
"""
from src.services.route_models import RoutePoint

from .parser import PosteData


def poste_to_routepoint(p: PosteData) -> RoutePoint | None:
    """
    Converte PosteData → RoutePoint.
    Retorna None se o poste não tiver coordenadas válidas.
    """
    if not p.has_coords:
        return None
    return RoutePoint(
        id=p.code,
        lat=p.lat,
        lon=p.lng,
        label=p.alimentador_principal,
    )


def postes_to_routepoints(postes: list[PosteData]) -> list[RoutePoint]:
    """Converte lista, descartando inválidos automaticamente."""
    return [rp for rp in (poste_to_routepoint(p) for p in postes) if rp is not None]


__all__ = ["poste_to_routepoint", "postes_to_routepoints"]
