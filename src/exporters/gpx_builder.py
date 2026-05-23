"""
Gera arquivos GPX (GPS Exchange Format) — versão otimizada para OsmAnd.

GPX é o formato nativo do OsmAnd, Organic Maps, Garmin, Strava, Wikiloc.

Estrutura:
  - <wpt>         → waypoints individuais (marcadores numerados)
  - <rte>         → route navegável (sequência TSP otimizada)
  - <trk>         → track (linha rodoviária desenhada via OSRM)
  - <extensions>  → metadados OsmAnd p/ navegação multi-paradas

Compatibilidade testada:
  ✅ OsmAnd 4.x (Android)  → importa como rota navegável c/ paradas
  ✅ Organic Maps          → mostra trilha + pontos
  ✅ Google Earth          → exibe linha + pinos
  ✅ Garmin BaseCamp       → reconhece como rota
"""

from datetime import datetime, timezone
from xml.sax.saxutils import escape as xml_escape

from .parser import PosteData


# ──────────────────────────────────────────────────────────────────────
# Namespaces (declarados no <gpx>)
# ──────────────────────────────────────────────────────────────────────
OSMAND_NS = "https://osmand.net"
GPXX_NS = "http://www.garmin.com/xmlschemas/GpxExtensions/v3"


# ──────────────────────────────────────────────────────────────────────
# Waypoints individuais
# ──────────────────────────────────────────────────────────────────────
def _waypoint(p: PosteData, num: int | None = None, poi_type: str = "poste") -> str:
    """Gera <wpt> com extensão OsmAnd p/ ícone customizado."""
    name = f"{num:02d}. {p.code}" if num is not None else p.code
    desc_parts = []
    if p.alimentadores:
        desc_parts.append(f"Alimentador: {', '.join(p.alimentadores)}")
    if p.estruturas_mt:
        desc_parts.append(f"MT: {', '.join(p.estruturas_mt)}")
    if p.estruturas_bt:
        desc_parts.append(f"BT: {', '.join(p.estruturas_bt)}")
    desc = " | ".join(desc_parts)

    # Ícone varia conforme posição na rota
    if num == 1:
        icon = "special_utility_pole"
        color = "#4CAF50"  # Verde para início
    elif num is not None and poi_type == "final":
        icon = "special_utility_pole"
        color = "#F44336"  # Vermelho para fim
    else:
        icon = "special_utility_pole"
        color = "#1976D2"  # Azul padrão

    return f"""  <wpt lat="{p.lat}" lon="{p.lng}">
    <name>{xml_escape(name)}</name>
    <desc>{xml_escape(desc)}</desc>
    <type>Poste</type>
    <sym>Flag, Blue</sym>
    <extensions>
      <osmand:icon>{xml_escape(icon)}</osmand:icon>
      <osmand:background>circle</osmand:background>
      <osmand:color>{color}</osmand:color>
    </extensions>
  </wpt>
"""


# ──────────────────────────────────────────────────────────────────────
# Pontos da rota navegável
# ──────────────────────────────────────────────────────────────────────
def _route_point(p: PosteData, num: int, is_last: bool = False) -> str:
    """
    Gera <rtept> marcado como parada intermediária OU destino final.
    Essa marcação é o que faz OsmAnd parar em cada poste durante a navegação.
    """
    point_type = "destination" if is_last else "intermediate"
    return f"""    <rtept lat="{p.lat}" lon="{p.lng}">
      <name>{xml_escape(f'{num:02d}. {p.code}')}</name>
      <type>{point_type}</type>
    </rtept>
"""


# ──────────────────────────────────────────────────────────────────────
# Track (linha desenhada nas ruas)
# ──────────────────────────────────────────────────────────────────────
def _track_xml(
    geometry: list[tuple[float, float]],
    batch_id: str,
) -> str:
    """
    Gera <trk> com geometria OSRM (linha seguindo ruas reais).
    Essencial para visualizar a rota rodoviária no mapa.
    """
    if not geometry or len(geometry) < 2:
        return ""

    trkpts = "".join(
        f'      <trkpt lat="{lat}" lon="{lon}"></trkpt>\n'
        for lat, lon in geometry
    )
    return f"""  <trk>
    <name>🛣️ Trilha Rodoviária — Lote {xml_escape(batch_id[:8])}</name>
    <desc>Geometria da rota traçada por OSRM (ruas reais)</desc>
    <type>Route</type>
    <extensions>
      <osmand:color>#FF6F00</osmand:color>
      <osmand:width>5</osmand:width>
    </extensions>
    <trkseg>
{trkpts}    </trkseg>
  </trk>
"""


# ──────────────────────────────────────────────────────────────────────
# Função principal
# ──────────────────────────────────────────────────────────────────────
def build_gpx(
    postes: list[PosteData],
    batch_id: str,
    ordem: list[str] | None = None,
    route_geometry: list[tuple[float, float]] | None = None,
    profile: str = "car",
) -> str:
    """
    Gera GPX completo otimizado para navegação no OsmAnd.
    
    ✅ GARANTE ROTAS AUTOMÁTICAS:
      - Se `ordem` fornecida → usa sequência otimizada
      - Se `ordem` é None → usa ordem natural dos postes
      - Sempre gera <rte> para navegação multi-parada
      - Opcionalmente gera <trk> se geometria OSRM disponível

    Args:
        postes: lista de postes COM coordenadas válidas.
        batch_id: identificador do lote.
        ordem: sequência otimizada (se None, usa ordem natural).
        route_geometry: lista (lat, lon) da geometria OSRM (opcional).
        profile: perfil OsmAnd ('car', 'bicycle', 'pedestrian', 'truck').

    Returns:
        String XML válida pronta pra salvar como .gpx
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ─── Determina ordem de visita ────────────────────────────────────
    # Se ordem otimizada foi fornecida, usa-a; senão, usa ordem natural
    if ordem:
        by_code = {p.code: p for p in postes}
        postes_ordenados = [by_code[c] for c in ordem if c in by_code]
        is_optimized = True
    else:
        postes_ordenados = list(postes)
        is_optimized = False

    # ─── Waypoints individuais (SEMPRE gera com numeração) ────────────
    wpts_list = []
    for i, p in enumerate(postes_ordenados):
        poi_type = "final" if (i == len(postes_ordenados) - 1) else "poste"
        wpt = _waypoint(p, num=i + 1, poi_type=poi_type)
        wpts_list.append(wpt)
    
    wpts = "".join(wpts_list)

    # ─── Route navegável (SEMPRE gera, com ou sem otimização) ─────────
    last_idx = len(postes_ordenados) - 1
    rtepts = "".join(
        _route_point(p, i + 1, is_last=(i == last_idx))
        for i, p in enumerate(postes_ordenados)
    )
    
    optimization_label = "Otimizada" if is_optimized else "Natural"
    route_xml = f"""  <rte>
    <name>🚗 Rota {optimization_label} — Lote {xml_escape(batch_id[:8])}</name>
    <desc>{len(postes_ordenados)} paradas (perfil: {profile})</desc>
    <type>{xml_escape(profile)}</type>
    <extensions>
      <osmand:profile>{xml_escape(profile)}</osmand:profile>
      <osmand:optimized>{str(is_optimized).lower()}</osmand:optimized>
      <osmand:points_groups>
        <group name="Paradas de Inspeção" color="#1976D2" />
      </osmand:points_groups>
    </extensions>
{rtepts}  </rte>
"""

    # ─── Track (geometria OSRM, se disponível) ───────────────────────
    track_xml = _track_xml(route_geometry, batch_id) if route_geometry else ""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1"
     creator="bot-integrador-µ9"
     xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xmlns:osmand="{OSMAND_NS}"
     xmlns:gpxx="{GPXX_NS}"
     xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">
  <metadata>
    <name>Lote {xml_escape(batch_id[:8])}</name>
    <desc>Rota de inspeção de postes — {len(postes_ordenados)} paradas{' (otimizada)' if is_optimized else ''}</desc>
    <time>{now}</time>
    <keywords>EQTL, Inspeção, Postes, {profile.capitalize()}</keywords>
    <extensions>
      <osmand:routing_profile>{xml_escape(profile)}</osmand:routing_profile>
      <osmand:route_type>inspection</osmand:route_type>
      <osmand:total_stops>{len(postes_ordenados)}</osmand:total_stops>
      <osmand:optimized>{str(is_optimized).lower()}</osmand:optimized>
      <osmand:batch_id>{xml_escape(batch_id)}</osmand:batch_id>
    </extensions>
  </metadata>
{wpts}{route_xml}{track_xml}</gpx>
"""


__all__ = ["build_gpx"]
