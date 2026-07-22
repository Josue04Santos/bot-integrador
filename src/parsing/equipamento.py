"""
Parser de EQUIPAMENTO/INSTALAÇÃO — texto bruto do @ReincidenciasBot → EquipamentoResultado.

Escrito do zero para alimentar diretamente as tabelas `equipamentos` e
`componentes` (ver src/database/models_estruturados.py). Corrige a
inconsistência do parser antigo (src/exporters/parser_equipamento.py), onde
o dataclass usava `tipo`/`componente` mas o model ORM (`Meter`) só tinha
`componente` — aqui `ComponenteResultado` já tem os mesmos nomes de coluna
da tabela `componentes` (`tipo`, `componente_code`, `elo`, `clientes`,
`trafos`).
"""

import re
from dataclasses import dataclass, field

from src.parsing.deteccao import is_not_found

RE_INSTALACAO = re.compile(r"Instalação:\s*\*\*([A-Z0-9]+)\*\*", re.IGNORECASE)
RE_COORDS = re.compile(r"place/(-?\d+\.\d+),\s*(-?\d+\.\d+)")
RE_ALIMENTADOR = re.compile(r"\*\*Alimentador:\s*\*\*([A-Z0-9\-]+)", re.IGNORECASE)
RE_PERIMETRO = re.compile(r"\*\*Perímetro:\s*\*\*([A-Z]+)", re.IGNORECASE)
RE_TIPO = re.compile(r"\*\*Tipo:\s*\*\*([^\n]+)", re.IGNORECASE)
RE_POSTE = re.compile(r"\*\*Poste:\s*\*\*(\d+)", re.IGNORECASE)
RE_POTENCIA = re.compile(r"\*\*Potência:\s*\*\*([^\n]+)", re.IGNORECASE)
RE_TENSAO_PRI = re.compile(r"\*\*Tensão\s+Primária:\s*\*\*([^\n]+)", re.IGNORECASE)
RE_TENSAO_SEC = re.compile(r"\*\*Tensão\s+Secundária:\s*\*\*([^\n]+)", re.IGNORECASE)
RE_FASE = re.compile(r"\*\*Fase:\s*\*\*([A-Z]+)", re.IGNORECASE)
RE_CLIENTES = re.compile(r"\*\*Clientes:\s*\*\*(\d+)", re.IGNORECASE)
RE_SITUACAO = re.compile(r"\*\*Situação:\s*\*\*([^\n]+)", re.IGNORECASE)

# Linha da tabela "CHAVES A MONTANTE": TIPO  CODE  [ELO]  CLIENTES  TRAFOS  [observação]
RE_LINHA_COMPONENTE = re.compile(
    r"^(FU|CF|RG|DJ|SE)\s+(\S+)\s+(?:(\S+)\s+)?(\d+)\s+(\d+)",
    re.MULTILINE,
)


def _limpar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto.replace("*", "")).strip()


def _inferir_tipo(raw: str, potencia: str, code: str) -> str:
    """Infere o tipo do equipamento quando o campo vem vazio do bot terceiro."""
    if "kva" in potencia.lower():
        return "Transformador"
    if code.upper().startswith("RG") or "RG " in raw[:200]:
        return "Religador"
    if "Chave Fusível" in raw or "FU " in raw[:300]:
        return "Chave Fusível"
    if code.upper().startswith("DJ") or "DJ " in raw[:200]:
        return "Disjuntor"
    if code.upper().startswith("SE"):
        return "Seccionalizador"
    return ""


@dataclass
class ComponenteResultado:
    """Uma chave a montante — campos 1:1 com a tabela `componentes`."""

    tipo: str  # FU | CF | RG | DJ | SE
    componente_code: str
    elo: str | None
    clientes: int
    trafos: int
    ordem: int


@dataclass
class EquipamentoResultado:
    """Resultado do parse de um equipamento — campos 1:1 com a tabela `equipamentos`."""

    code: str
    ok: bool
    motivo: str | None = None  # None | "nao_encontrado" | "resposta_vazia"

    instalacao: str = ""
    tipo: str = ""
    poste_referencia: str = ""
    potencia: str = ""
    tensao_primaria: str = ""
    tensao_secundaria: str = ""
    fase: str = ""
    clientes_total: int | None = None
    situacao: str = ""
    perimetro: str = ""
    alimentador: str = ""

    latitude: float | None = None
    longitude: float | None = None

    componentes: list[ComponenteResultado] = field(default_factory=list)


def parse_equipamento(code: str, raw: str | None) -> EquipamentoResultado:
    """Faz o parse do texto bruto retornado pelo bot terceiro para um equipamento."""
    if not raw or not raw.strip():
        return EquipamentoResultado(code=code, ok=False, motivo="resposta_vazia")

    if is_not_found(raw):
        return EquipamentoResultado(code=code, ok=False, motivo="nao_encontrado")

    resultado = EquipamentoResultado(code=code, ok=True)

    m = RE_INSTALACAO.search(raw)
    resultado.instalacao = m.group(1) if m else code

    m = RE_COORDS.search(raw)
    if m:
        resultado.latitude = float(m.group(1))
        resultado.longitude = float(m.group(2))

    m = RE_ALIMENTADOR.search(raw)
    if m:
        resultado.alimentador = _limpar(m.group(1))

    m = RE_PERIMETRO.search(raw)
    if m:
        resultado.perimetro = _limpar(m.group(1))

    m = RE_TIPO.search(raw)
    if m:
        resultado.tipo = _limpar(m.group(1))

    m = RE_POSTE.search(raw)
    if m:
        resultado.poste_referencia = m.group(1)

    m = RE_POTENCIA.search(raw)
    if m:
        resultado.potencia = _limpar(m.group(1))

    m = RE_TENSAO_PRI.search(raw)
    if m:
        resultado.tensao_primaria = _limpar(m.group(1))

    m = RE_TENSAO_SEC.search(raw)
    if m:
        resultado.tensao_secundaria = _limpar(m.group(1))

    m = RE_FASE.search(raw)
    if m:
        resultado.fase = m.group(1).strip()

    m = RE_CLIENTES.search(raw)
    if m:
        resultado.clientes_total = int(m.group(1))

    m = RE_SITUACAO.search(raw)
    if m:
        resultado.situacao = _limpar(m.group(1))

    if not resultado.tipo:
        resultado.tipo = _inferir_tipo(raw, resultado.potencia, code)

    for ordem, m in enumerate(RE_LINHA_COMPONENTE.finditer(raw)):
        resultado.componentes.append(ComponenteResultado(
            tipo=m.group(1),
            componente_code=m.group(2),
            elo=m.group(3),
            clientes=int(m.group(4)),
            trafos=int(m.group(5)),
            ordem=ordem,
        ))

    return resultado
