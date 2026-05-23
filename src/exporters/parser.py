"""
Parser do raw_response do bot remoto DPL Construções.

Extrai: código, lat, lng, alimentador(es), cabo(s), estruturas MT/BT.

Resiliente a variações de formatação (texto não é estruturado).
"""

import re
from dataclasses import dataclass, field


# Regex compiladas (performance)
RE_POSTE      = re.compile(r"Poste\s*:\s*(\d+)", re.IGNORECASE)
RE_COORDS     = re.compile(r"place/(-?\d+\.\d+),\s*(-?\d+\.\d+)")

# FIX bug#1: aceita "**Alimentador **IBS09F1" ou "Alimentador: IBS09F1"
# Captura o token alfanumérico que vier depois (ignora **, :, espaços)
RE_ALIMENT    = re.compile(
    r"Alimentador[\s\*:\-]*([A-Z][A-Z0-9_\-]{2,})",
    re.IGNORECASE,
)

# FIX bug#2: captura o cabo limpo (sem **) entre "Cabo" e "[MT/BT]"
RE_CABO       = re.compile(
    r"Cabo[\s\*:\-]*([^\n\[\*]+?)\s*\[(MT|BT)\]",
    re.IGNORECASE,
)

RE_ESTRUT_MT  = re.compile(r"MT\s*:\s*((?:\[[^\]]+\]\s*)+)", re.IGNORECASE)
RE_ESTRUT_BT  = re.compile(r"BT\s*:\s*((?:\[[^\]]+\]\s*)+)", re.IGNORECASE)
RE_NIVEL      = re.compile(r"\[\s*nivel\s+\d+\s+([A-Z0-9]+)\s*\]", re.IGNORECASE)


def _clean(text: str) -> str:
    """Remove asteriscos de markdown, espaços duplos e bordas."""
    return re.sub(r"\s+", " ", text.replace("*", "")).strip()


@dataclass
class PosteData:
    """Dados estruturados de um poste, prontos para o KML."""
    code: str
    lat: float | None = None
    lng: float | None = None
    alimentadores: list[str] = field(default_factory=list)
    cabos_mt: list[str] = field(default_factory=list)
    cabos_bt: list[str] = field(default_factory=list)
    estruturas_mt: list[str] = field(default_factory=list)
    estruturas_bt: list[str] = field(default_factory=list)
    raw: str = ""
    parse_error: str | None = None

    @property
    def has_coords(self) -> bool:
        return self.lat is not None and self.lng is not None

    @property
    def alimentador_principal(self) -> str:
        return self.alimentadores[0] if self.alimentadores else "SEM_ALIMENTADOR"


def parse_poste_response(code: str, raw: str | None) -> PosteData:
    """
    Faz o parse do texto bruto retornado pelo bot remoto.
    Sempre retorna PosteData (mesmo em erro — use .parse_error pra detectar).
    """
    data = PosteData(code=code, raw=raw or "")

    if not raw:
        data.parse_error = "raw_response vazio"
        return data

    try:
        # Coordenadas
        m = RE_COORDS.search(raw)
        if m:
            data.lat = float(m.group(1))
            data.lng = float(m.group(2))

        # Alimentadores (dedup preservando ordem)
        data.alimentadores = list(dict.fromkeys(
            _clean(m.group(1)) for m in RE_ALIMENT.finditer(raw)
        ))

        # Cabos por tensão (limpos)
        for m in RE_CABO.finditer(raw):
            cabo = _clean(m.group(1))
            tensao = m.group(2).upper()
            if cabo:
                (data.cabos_mt if tensao == "MT" else data.cabos_bt).append(cabo)

        # Estruturas MT
        m_mt = RE_ESTRUT_MT.search(raw)
        if m_mt:
            data.estruturas_mt = [n.group(1) for n in RE_NIVEL.finditer(m_mt.group(1))]

        # Estruturas BT
        m_bt = RE_ESTRUT_BT.search(raw)
        if m_bt:
            data.estruturas_bt = [n.group(1) for n in RE_NIVEL.finditer(m_bt.group(1))]

    except Exception as e:
        data.parse_error = f"{type(e).__name__}: {e}"

    return data
