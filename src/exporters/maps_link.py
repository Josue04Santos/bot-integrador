"""
Geradores de URLs pra abrir rotas em apps de mapas comerciais.

- Google Maps: aceita até 10 waypoints por URL → chunking se >10
- Waze:        só destino único (não suporta multi-stop)
"""

from urllib.parse import quote

from .parser import PosteData


GOOGLE_MAPS_MAX_WAYPOINTS = 10


def build_google_maps_urls(postes_ordenados: list[PosteData]) -> list[str]:
    """
    Retorna lista de URLs do Google Maps Directions.
    Cada URL contém até 10 paradas (limitação do Google).

    Exemplo:
        15 postes → 2 URLs (10 + 6 com sobreposição do último ponto)
    """
    postes_validos = [p for p in postes_ordenados if p.has_coords]
    if len(postes_validos) < 2:
        return []

    urls = []
    i = 0
    while i < len(postes_validos):
        chunk = postes_validos[i:i + GOOGLE_MAPS_MAX_WAYPOINTS]
        coords = "/".join(f"{p.lat},{p.lng}" for p in chunk)
        urls.append(f"https://www.google.com/maps/dir/{coords}")
        # Sobreposição: próximo chunk começa no último ponto do anterior
        i += GOOGLE_MAPS_MAX_WAYPOINTS - 1

    return urls


def build_waze_url(poste: PosteData) -> str:
    """URL Waze pra navegar até UM poste específico."""
    if not poste.has_coords:
        return ""
    return f"https://waze.com/ul?ll={poste.lat},{poste.lng}&navigate=yes"


def build_osmand_url(poste: PosteData) -> str:
    """
    URL OsmAnd (geo: scheme universal).
    Funciona também em outros apps que suportam o protocolo geo:.
    """
    if not poste.has_coords:
        return ""
    label = quote(poste.code)
    return f"geo:{poste.lat},{poste.lng}?q={poste.lat},{poste.lng}({label})"


__all__ = ["build_google_maps_urls", "build_waze_url", "build_osmand_url"]
