"""Exportação CSV paralela ao KML (Excel-friendly, UTF-8 com BOM)."""

import csv
import io

from .parser import PosteData


CSV_HEADERS = [
    "codigo", "latitude", "longitude",
    "alimentadores", "estruturas_mt", "estruturas_bt",
    "cabos_mt", "cabos_bt", "tem_coords", "erro",
]


def build_csv(postes: list[PosteData]) -> bytes:
    """
    Retorna o CSV em bytes (UTF-8 + BOM para Excel BR abrir bonito).
    Inclui TODOS os postes (com e sem coordenadas).
    """
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(CSV_HEADERS)

    for p in postes:
        writer.writerow([
            p.code,
            f"{p.lat:.10f}".replace(".", ",") if p.lat is not None else "",
            f"{p.lng:.10f}".replace(".", ",") if p.lng is not None else "",
            " | ".join(p.alimentadores),
            " | ".join(p.estruturas_mt),
            " | ".join(p.estruturas_bt),
            " / ".join(p.cabos_mt),
            " / ".join(p.cabos_bt),
            "SIM" if p.has_coords else "NÃO",
            p.parse_error or "",
        ])

    # UTF-8 com BOM (\ufeff) → Excel BR abre com acentos OK
    return ("\ufeff" + buf.getvalue()).encode("utf-8")
