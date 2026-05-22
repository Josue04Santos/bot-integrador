"""
Estilos KML: ícones e cores por tipo de tensão.

Usamos os ícones oficiais do Google Earth (paddle/shapes),
que são reconhecidos por todos os apps compatíveis (Locus, MAPinr, Earth, etc.)
"""

# Pinos coloridos do Google Earth (padrão universal)
ICON_BASE = "http://maps.google.com/mapfiles/kml/paddle"

# Mapa: categoria → (id_estilo, url_icone, cor_hex_AABBGGRR, label)
STYLES = {
    "MT":      ("style_mt",   f"{ICON_BASE}/ylw-circle.png", "ff00ffff", "Média Tensão"),
    "BT":      ("style_bt",   f"{ICON_BASE}/blu-circle.png", "ffff0000", "Baixa Tensão"),
    "MT_BT":   ("style_mtbt", f"{ICON_BASE}/grn-circle.png", "ff00ff00", "MT + BT"),
    "NONE":    ("style_none", f"{ICON_BASE}/wht-circle.png", "ffcccccc", "Sem estrutura"),
    "ERROR":   ("style_err",  f"{ICON_BASE}/red-circle.png", "ff0000ff", "Erro"),
}

# Cores das LineStrings por alimentador (rotaciona entre estas)
LINE_COLORS = [
    "ff00ffff",  # amarelo
    "ffff8800",  # laranja
    "ffff00ff",  # magenta
    "ff00ff88",  # verde-água
    "ff8800ff",  # roxo
    "ff0088ff",  # azul-claro
]


def categorize(estruturas_mt: list[str], estruturas_bt: list[str]) -> str:
    """Decide a categoria visual do poste."""
    has_mt = bool(estruturas_mt)
    has_bt = bool(estruturas_bt)
    if has_mt and has_bt:
        return "MT_BT"
    if has_mt:
        return "MT"
    if has_bt:
        return "BT"
    return "NONE"
