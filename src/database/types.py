"""
Tipos customizados portáveis SQLite ↔ Postgres.
"""
import os
import time
import uuid
from typing import Optional


def uuid7() -> str:
    """
    Gera UUID v7 (RFC 9562) — ordenável por tempo.
    
    Estrutura: [48 bits timestamp ms][4 bits version=7][12 bits rand_a]
               [2 bits variant=10][62 bits rand_b]
    
    Vantagens sobre UUID v4:
    - Ordenável cronologicamente (índices B-tree eficientes)
    - Permite filtros por data sem coluna extra
    - Portável SQLite/Postgres/MySQL
    
    Returns:
        String UUID no formato '01928f00-1234-7abc-89de-f0123456789a'
    """
    ts_ms = int(time.time() * 1000)
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), "big") & 0x3FFFFFFFFFFFFFFF
    
    uuid_int = (
        (ts_ms & 0xFFFFFFFFFFFF) << 80
        | (0x7 << 76)
        | (rand_a << 64)
        | (0x2 << 62)
        | rand_b
    )
    
    h = f"{uuid_int:032x}"
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def uuid7_timestamp(uuid_str: str) -> Optional[float]:
    """
    Extrai o timestamp (em segundos) de um UUID v7.
    Útil para debug/auditoria sem coluna de data.
    """
    try:
        hex_clean = uuid_str.replace("-", "")
        ts_ms = int(hex_clean[:12], 16)
        return ts_ms / 1000.0
    except (ValueError, IndexError):
        return None
