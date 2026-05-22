"""
Gera o XML KML a partir de uma lista de PosteData.

Recursos:
- Folders por alimentador
- Ícones diferentes por tensão (MT/BT/MT+BT)
- LineStrings ligando postes do mesmo alimentador
- Header com estatísticas
- HTML rico na descrição de cada Placemark
"""

from datetime import datetime
from html import escape
from xml.sax.saxutils import escape as xml_escape

from .parser import PosteData
from .styles import LINE_COLORS, STYLES, categorize


def _build_styles_xml() -> str:
    """Define todos os <Style> no início do KML."""
    parts = []
    for sid, url, color, _label in STYLES.values():
        parts.append(f"""
    <Style id="{sid}">
      <IconStyle>
        <color>{color}</color>
        <scale>1.1</scale>
        <Icon><href>{url}</href></Icon>
      </IconStyle>
      <LabelStyle><scale>0.85</scale></LabelStyle>
    </Style>""")

    # Estilos das LineStrings por alimentador
    for i, color in enumerate(LINE_COLORS):
        parts.append(f"""
    <Style id="line_{i}">
      <LineStyle>
        <color>{color}</color>
        <width>2.5</width>
      </LineStyle>
    </Style>""")

    return "".join(parts)


def _placemark_description(p: PosteData) -> str:
    """HTML rico que aparece ao clicar no pino."""
    rows = []
    if p.alimentadores:
        rows.append(f"<b>Alimentador(es):</b> {escape(', '.join(p.alimentadores))}")
    if p.estruturas_mt:
        rows.append(f"<b>Estruturas MT:</b> {escape(', '.join(p.estruturas_mt))}")
    if p.estruturas_bt:
        rows.append(f"<b>Estruturas BT:</b> {escape(', '.join(p.estruturas_bt))}")
    if p.cabos_mt:
        rows.append(f"<b>Cabo MT:</b> {escape(' / '.join(p.cabos_mt))}")
    if p.cabos_bt:
        rows.append(f"<b>Cabo BT:</b> {escape(' / '.join(p.cabos_bt))}")
    rows.append(f"<b>Coords:</b> {p.lat}, {p.lng}")
    body = "<br/>".join(rows)
    return f"<![CDATA[{body}]]>"


def _build_placemark(p: PosteData) -> str:
    cat = categorize(p.estruturas_mt, p.estruturas_bt)
    style_id = STYLES[cat][0]
    return f"""
      <Placemark>
        <name>{xml_escape(p.code)}</name>
        <styleUrl>#{style_id}</styleUrl>
        <description>{_placemark_description(p)}</description>
        <Point>
          <coordinates>{p.lng},{p.lat},0</coordinates>
        </Point>
      </Placemark>"""


def _build_linestring(alimentador: str, postes: list[PosteData], color_idx: int) -> str:
    """Liga postes do mesmo alimentador com uma linha."""
    if len(postes) < 2:
        return ""
    coords = " ".join(f"{p.lng},{p.lat},0" for p in postes if p.has_coords)
    if not coords.strip():
        return ""
    return f"""
      <Placemark>
        <name>Rede {xml_escape(alimentador)}</name>
        <styleUrl>#line_{color_idx % len(LINE_COLORS)}</styleUrl>
        <LineString>
          <tessellate>1</tessellate>
          <coordinates>{coords}</coordinates>
        </LineString>
      </Placemark>"""


def _stats_html(postes: list[PosteData], invalidos: list[PosteData]) -> str:
    total = len(postes) + len(invalidos)
    com_coords = len(postes)
    mt = sum(1 for p in postes if p.estruturas_mt)
    bt = sum(1 for p in postes if p.estruturas_bt)
    alimentadores = sorted({p.alimentador_principal for p in postes})
    body = f"""
<b>📊 Estatísticas do Lote</b><br/>
Total consultado: {total}<br/>
Com coordenadas: {com_coords}<br/>
Sem coordenadas: {len(invalidos)}<br/>
Com estruturas MT: {mt}<br/>
Com estruturas BT: {bt}<br/>
Alimentadores: {len(alimentadores)} ({escape(', '.join(alimentadores))})<br/>
Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
"""
    return f"<![CDATA[{body}]]>"


def build_kml(
    postes: list[PosteData],
    batch_id: str,
    invalidos: list[PosteData] | None = None,
) -> str:
    """
    Gera o XML KML completo.
    `postes` = somente os que têm coordenadas válidas.
    `invalidos` = vão pro arquivo .txt separado (não entram no KML).
    """
    invalidos = invalidos or []

    # Agrupa por alimentador
    grupos: dict[str, list[PosteData]] = {}
    for p in postes:
        grupos.setdefault(p.alimentador_principal, []).append(p)

    folders_xml = []
    for idx, (alim, lista) in enumerate(sorted(grupos.items())):
        placemarks = "".join(_build_placemark(p) for p in lista)
        line = _build_linestring(alim, lista, idx)
        folders_xml.append(f"""
    <Folder>
      <name>{xml_escape(alim)} ({len(lista)} poste{'s' if len(lista) != 1 else ''})</name>
      <open>1</open>{placemarks}{line}
    </Folder>""")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Lote {xml_escape(batch_id)}</name>
    <description>{_stats_html(postes, invalidos)}</description>
{_build_styles_xml()}
{''.join(folders_xml)}
  </Document>
</kml>
"""


def build_invalidos_txt(invalidos: list[PosteData]) -> str:
    """Relatório TXT dos postes sem coordenada."""
    if not invalidos:
        return ""
    lines = ["# Postes SEM coordenadas (não incluídos no KML)", ""]
    for p in invalidos:
        motivo = p.parse_error or "coordenadas ausentes na resposta"
        lines.append(f"- {p.code}: {motivo}")
    lines.append("")
    lines.append(f"Total: {len(invalidos)} poste(s)")
    return "\n".join(lines)
