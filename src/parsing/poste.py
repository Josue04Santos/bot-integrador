"""
Parser de POSTE — texto bruto do @ReincidenciasBot → PosteResultado.

Escrito do zero para alimentar diretamente a tabela `postes` (ver
src/database/models_estruturados.py), sem herdar as inconsistências do
parser antigo (src/exporters/parser.py).
"""

import re
from dataclasses import dataclass, field

from src.parsing.deteccao import is_not_found

RE_COORDS = re.compile(r"place/(-?\d+\.\d+),\s*(-?\d+\.\d+)")

RE_ALIMENTADOR = re.compile(
    r"Alimentador[\s\*:\-]*([A-Z][A-Z0-9_\-]{2,})",
    re.IGNORECASE,
)

RE_CABO = re.compile(
    r"Cabo[\s\*:\-]*([^\n\[\*]+?)\s*\[(MT|BT)\]",
    re.IGNORECASE,
)

RE_ESTRUTURAS_MT = re.compile(r"MT\s*:\s*((?:\[[^\]]+\]\s*)+)", re.IGNORECASE)
RE_ESTRUTURAS_BT = re.compile(r"BT\s*:\s*((?:\[[^\]]+\]\s*)+)", re.IGNORECASE)
RE_NIVEL = re.compile(r"\[\s*nivel\s+\d+\s+([A-Z0-9]+)\s*\]", re.IGNORECASE)


def _limpar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto.replace("*", "")).strip()


@dataclass
class PosteResultado:
    """Resultado do parse de um poste — campos 1:1 com a tabela `postes`."""

    code: str
    ok: bool
    motivo: str | None = None  # None | "nao_encontrado" | "resposta_vazia"

    latitude: float | None = None
    longitude: float | None = None
    alimentadores: list[str] = field(default_factory=list)
    cabos_mt: list[str] = field(default_factory=list)
    cabos_bt: list[str] = field(default_factory=list)
    estruturas_mt: list[str] = field(default_factory=list)
    estruturas_bt: list[str] = field(default_factory=list)


def parse_poste(code: str, raw: str | None) -> PosteResultado:
    """Faz o parse do texto bruto retornado pelo bot terceiro para um poste."""
    if not raw or not raw.strip():
        return PosteResultado(code=code, ok=False, motivo="resposta_vazia")

    if is_not_found(raw):
        return PosteResultado(code=code, ok=False, motivo="nao_encontrado")

    resultado = PosteResultado(code=code, ok=True)

    m = RE_COORDS.search(raw)
    if m:
        resultado.latitude = float(m.group(1))
        resultado.longitude = float(m.group(2))

    resultado.alimentadores = list(dict.fromkeys(
        _limpar(m.group(1)) for m in RE_ALIMENTADOR.finditer(raw)
    ))

    for m in RE_CABO.finditer(raw):
        cabo = _limpar(m.group(1))
        tensao = m.group(2).upper()
        if cabo:
            (resultado.cabos_mt if tensao == "MT" else resultado.cabos_bt).append(cabo)

    m_mt = RE_ESTRUTURAS_MT.search(raw)
    if m_mt:
        resultado.estruturas_mt = [n.group(1) for n in RE_NIVEL.finditer(m_mt.group(1))]

    m_bt = RE_ESTRUTURAS_BT.search(raw)
    if m_bt:
        resultado.estruturas_bt = [n.group(1) for n in RE_NIVEL.finditer(m_bt.group(1))]

    return resultado
