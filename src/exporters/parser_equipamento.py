"""
Parser do raw_response de EQUIPAMENTOS/INSTALAÇÕES.

Extrai: código, tipo, poste referência, potência, tensão, fase, clientes,
        situação, perímetro, alimentador, coordenadas, chaves a montante.
"""

import re
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════
# REGEX COMPILADAS (performance + manutenibilidade)
# ═══════════════════════════════════════════════════════════

RE_INSTALACAO = re.compile(r"Instalação:\s*\*\*([A-Z0-9]+)\*\*", re.IGNORECASE)
RE_COORDS     = re.compile(r"place/(-?\d+\.\d+),\s*(-?\d+\.\d+)")
RE_ALIMENTADOR = re.compile(r"\*\*Alimentador:\s*\*\*([A-Z0-9\-]+)", re.IGNORECASE)
RE_PERIMETRO  = re.compile(r"\*\*Perímetro:\s*\*\*([A-Z]+)", re.IGNORECASE)
RE_TIPO       = re.compile(r"\*\*Tipo:\s*\*\*([^\n]+)", re.IGNORECASE)
RE_POSTE      = re.compile(r"\*\*Poste:\s*\*\*(\d+)", re.IGNORECASE)
RE_POTENCIA   = re.compile(r"\*\*Potência:\s*\*\*([^\n]+)", re.IGNORECASE)
RE_TENSAO_PRI = re.compile(r"\*\*Tensão\s+Primária:\s*\*\*([^\n]+)", re.IGNORECASE)
RE_TENSAO_SEC = re.compile(r"\*\*Tensão\s+Secundária:\s*\*\*([^\n]+)", re.IGNORECASE)
RE_FASE       = re.compile(r"\*\*Fase:\s*\*\*([A-Z]+)", re.IGNORECASE)
RE_CLIENTES   = re.compile(r"\*\*Clientes:\s*\*\*(\d+)", re.IGNORECASE)
RE_SITUACAO   = re.compile(r"\*\*Situação:\s*\*\*([^\n]+)", re.IGNORECASE)

# Tabela de chaves a montante — REGEX CORRIGIDA
RE_TABELA_LINHA = re.compile(
    r"^(FU|CF|RG|DJ|SE)\s+(\S+)\s+(?:(\S+)\s+)?(\d+)\s+(\d+)",
    re.MULTILINE
)


def _clean(text: str) -> str:
    """Remove asteriscos de markdown e espaços extras."""
    return re.sub(r"\s+", " ", text.replace("*", "")).strip()


def _inferir_tipo(raw: str, potencia: str, codigo: str) -> str:
    """Infere o tipo quando o campo vem vazio do bot remoto."""
    if "kVA" in potencia or "kva" in potencia.lower():
        return "Transformador"
    if codigo.upper().startswith("RG") or "RG " in raw[:200]:
        return "Religador"
    if "Chave Fusível" in raw or "FU " in raw[:300]:
        return "Chave Fusível"
    if codigo.upper().startswith("DJ") or "DJ " in raw[:200]:
        return "Disjuntor"
    if codigo.upper().startswith("SE"):
        return "Seccionalizador"
    return ""


@dataclass
class ChaveMontante:
    """Representa uma chave na hierarquia de proteção."""
    tipo: str  # FU, CF, RG, DJ, SE
    componente: str
    elo: str
    clientes: int
    trafos: int


@dataclass
class EquipamentoData:
    """Dados estruturados de um equipamento/instalação."""
    code: str
    instalacao: str = ""
    tipo: str = ""
    poste_referencia: str = ""  # 🔗 cross-reference com CSV de postes
    potencia: str = ""
    tensao_primaria: str = ""
    tensao_secundaria: str = ""
    fase: str = ""
    clientes: int = 0
    situacao: str = ""
    perimetro: str = ""
    alimentador: str = ""
    
    lat: float | None = None
    lng: float | None = None
    
    chaves_montante: list[ChaveMontante] = field(default_factory=list)
    
    raw: str = ""
    parse_error: str | None = None

    @property
    def has_coords(self) -> bool:
        return self.lat is not None and self.lng is not None

    @property
    def coords_str(self) -> str:
        """Retorna coordenadas formatadas para CSV."""
        if self.has_coords:
            return f"{self.lat}, {self.lng}"
        return ""

    @property
    def google_maps_link(self) -> str:
        """Gera link do Google Maps (corrige bug https//www → https://)."""
        if self.has_coords:
            return f"https://www.google.com.br/maps/place/{self.lat},{self.lng}"
        return ""

    @property
    def total_clientes_montante(self) -> int:
        """Total de clientes a montante (última linha da tabela)."""
        return self.chaves_montante[-1].clientes if self.chaves_montante else 0

    @property
    def total_trafos_montante(self) -> int:
        """Total de transformadores a montante (última linha da tabela)."""
        return self.chaves_montante[-1].trafos if self.chaves_montante else 0


def parse_equipamento_response(code: str, raw: str | None) -> EquipamentoData:
    """
    Faz o parse do texto bruto retornado pelo bot remoto (equipamento).
    Sempre retorna EquipamentoData (mesmo em erro — use .parse_error pra detectar).
    """
    data = EquipamentoData(code=code, raw=raw or "")

    if not raw:
        data.parse_error = "raw_response vazio"
        return data

    try:
        # Instalação
        m = RE_INSTALACAO.search(raw)
        if m:
            data.instalacao = m.group(1)

        # Coordenadas
        m = RE_COORDS.search(raw)
        if m:
            data.lat = float(m.group(1))
            data.lng = float(m.group(2))

        # Alimentador
        m = RE_ALIMENTADOR.search(raw)
        if m:
            data.alimentador = _clean(m.group(1))

        # Perímetro
        m = RE_PERIMETRO.search(raw)
        if m:
            data.perimetro = _clean(m.group(1))

        # Tipo
        m = RE_TIPO.search(raw)
        if m:
            data.tipo = _clean(m.group(1))

        # Poste referência (🔗 cross-reference!)
        m = RE_POSTE.search(raw)
        if m:
            data.poste_referencia = m.group(1)

        # Potência
        m = RE_POTENCIA.search(raw)
        if m:
            data.potencia = _clean(m.group(1))

        # Tensão Primária
        m = RE_TENSAO_PRI.search(raw)
        if m:
            data.tensao_primaria = _clean(m.group(1))

        # Tensão Secundária
        m = RE_TENSAO_SEC.search(raw)
        if m:
            data.tensao_secundaria = _clean(m.group(1))

        # Fase
        m = RE_FASE.search(raw)
        if m:
            data.fase = m.group(1).strip()

        # Clientes
        m = RE_CLIENTES.search(raw)
        if m:
            data.clientes = int(m.group(1))

        # Situação
        m = RE_SITUACAO.search(raw)
        if m:
            data.situacao = _clean(m.group(1))

        # 🆕 Inferir tipo se veio vazio
        if not data.tipo:
            data.tipo = _inferir_tipo(raw, data.potencia, code)

        # 🔧 Tabela de chaves a montante — CORRIGIDA
        for match in RE_TABELA_LINHA.finditer(raw):
            tipo_chave = match.group(1)
            componente = match.group(2)
            elo = match.group(3) or ""
            clientes = int(match.group(4))
            trafos = int(match.group(5))
            
            chave = ChaveMontante(
                tipo=tipo_chave,
                componente=componente,
                elo=elo,
                clientes=clientes,
                trafos=trafos,
            )
            data.chaves_montante.append(chave)

    except Exception as e:
        data.parse_error = f"{type(e).__name__}: {e}"

    return data
