"""
Construtor de CSV para equipamentos/instalações.

Colunas otimizadas para análise no Power BI / Excel.
"""

import io
import csv
from .parser_equipamento import EquipamentoData


def build_csv(equipamentos: list[EquipamentoData]) -> bytes:
    """
    Gera CSV UTF-8 com BOM (pra abrir certo no Excel).
    
    Colunas incluem cross-reference com postes via 'poste_referencia'.
    """
    buf = io.StringIO()
    
    # UTF-8 BOM (Excel reconhece automaticamente)
    buf.write("\ufeff")
    
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    
    # Cabeçalho
    writer.writerow([
        "codigo",
        "instalacao",
        "tipo",
        "poste_referencia",  # 🔗 para VLOOKUP com CSV de postes
        "alimentador",
        "perimetro",
        "potencia",
        "tensao_primaria",
        "tensao_secundaria",  # 🆕
        "fase",
        "clientes_diretos",
        "clientes_montante",
        "trafos_montante",
        "situacao",
        "latitude",
        "longitude",
        "coordenadas",
        "google_maps",
        "parse_error",
    ])
    
    # Dados
    for e in equipamentos:
        writer.writerow([
            e.code,
            e.instalacao,
            e.tipo,
            e.poste_referencia,
            e.alimentador,
            e.perimetro,
            e.potencia,
            e.tensao_primaria,
            e.tensao_secundaria,  # 🆕
            e.fase,
            e.clientes,
            e.total_clientes_montante,
            e.total_trafos_montante,
            e.situacao,
            e.lat if e.lat else "",
            e.lng if e.lng else "",
            e.coords_str,
            e.google_maps_link,
            e.parse_error or "",
        ])
    
    return buf.getvalue().encode("utf-8")
