"""
Gera GPX para equipamentos/instalações.

Diferente de postes (rota navegável), equipamentos são apenas waypoints
marcados no mapa com detalhes técnicos (tipo, alimentador, clientes, etc).

Compatível com: OsmAnd, Organic Maps, Google Earth, Garmin BaseCamp.
"""

from datetime import datetime, timezone
from xml.sax.saxutils import escape as xml_escape

from .parser_equipamento import EquipamentoData


OSMAND_NS = "https://osmand.net"


def _equipamento_waypoint(e: EquipamentoData, num: int) -> str:
    """Gera <wpt> para um equipamento com extensões OsmAnd."""
    
    # Nome: "01. 1262963" (numerado)
    name = f"{num:02d}. {e.code}"
    
    # Descrição: tipo, alimentador, clientes, etc
    desc_parts = []
    if e.tipo:
        desc_parts.append(f"Tipo: {e.tipo}")
    if e.instalacao:
        desc_parts.append(f"Instalação: {e.instalacao}")
    if e.alimentador:
        desc_parts.append(f"Alimentador: {e.alimentador}")
    if e.perimetro:
        desc_parts.append(f"Perímetro: {e.perimetro}")
    if e.potencia:
        desc_parts.append(f"Potência: {e.potencia}")
    if e.tensao_primaria:
        desc_parts.append(f"Tensão Primária: {e.tensao_primaria}")
    if e.tensao_secundaria:
        desc_parts.append(f"Tensão Secundária: {e.tensao_secundaria}")
    if e.clientes:
        desc_parts.append(f"Clientes Diretos: {e.clientes}")
    if e.total_clientes_montante:
        desc_parts.append(f"Clientes Montante: {e.total_clientes_montante}")
    if e.total_trafos_montante:
        desc_parts.append(f"Trafos Montante: {e.total_trafos_montante}")
    if e.fase:
        desc_parts.append(f"Fase: {e.fase}")
    if e.situacao:
        desc_parts.append(f"Situação: {e.situacao}")
    if e.poste_referencia:
        desc_parts.append(f"Poste Ref: {e.poste_referencia}")
    
    desc = " | ".join(desc_parts)
    
    # Ícone por tipo de equipamento
    if "Chave" in (e.tipo or ""):
        icon = "special_equipment"
        color = "#FF9800"  # Laranja para chaves
    elif "Transformador" in (e.tipo or ""):
        icon = "special_transformer"
        color = "#E91E63"  # Rosa para transformadores
    else:
        icon = "special_equipment"
        color = "#00BCD4"  # Ciano padrão
    
    return f"""  <wpt lat="{e.lat}" lon="{e.lng}">
    <name>{xml_escape(name)}</name>
    <desc>{xml_escape(desc)}</desc>
    <type>{xml_escape(e.tipo or "Equipamento")}</type>
    <extensions>
      <osmand:icon>{xml_escape(icon)}</osmand:icon>
      <osmand:background>circle</osmand:background>
      <osmand:color>{color}</osmand:color>
    </extensions>
  </wpt>
"""


def build_gpx_equipamentos(
    equipamentos: list[EquipamentoData],
    batch_id: str,
) -> str:
    """
    Gera GPX com waypoints de equipamentos (sem rota navegável).
    
    Equipamentos são apenas marcadores no mapa, sem otimização de rota.
    
    Args:
        equipamentos: lista de equipamentos COM coordenadas válidas.
        batch_id: identificador do lote.
    
    Returns:
        String XML válida pronta pra salvar como .gpx
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Gera waypoints numerados
    wpts_list = []
    for i, e in enumerate(equipamentos):
        wpt = _equipamento_waypoint(e, i + 1)
        wpts_list.append(wpt)
    
    wpts = "".join(wpts_list)
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1"
     creator="bot-integrador-µ9"
     xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xmlns:osmand="{OSMAND_NS}"
     xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">
  <metadata>
    <name>⚡ Equipamentos — Lote {xml_escape(batch_id[:8])}</name>
    <desc>Equipamentos/Instalações para inspeção no OsmAnd</desc>
    <author>
      <name>bot-integrador-µ9</name>
    </author>
    <copyright author="Distribuidora de Energia">
      <year>2026</year>
    </copyright>
    <time>{now}</time>
    <keywords>equipamentos, instalações, subestação, trafo, chave</keywords>
    <bounds minlat="-90" minlon="-180" maxlat="90" maxlon="180" />
  </metadata>
{wpts}
</gpx>
"""
