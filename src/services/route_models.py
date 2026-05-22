"""
Modelos de dados do µ9 — Route Optimizer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class RoutePoint:
    """Ponto geográfico (poste, depósito, parada)."""
    id: str
    lat: float
    lon: float
    label: str = ""

    def __post_init__(self):
        if not (-90.0 <= self.lat <= 90.0):
            raise ValueError(f"Latitude inválida: {self.lat} (esperado entre -90 e 90)")
        if not (-180.0 <= self.lon <= 180.0):
            raise ValueError(f"Longitude inválida: {self.lon} (esperado entre -180 e 180)")
        if not self.id:
            raise ValueError("RoutePoint.id não pode ser vazio")


@dataclass
class RouteResult:
    """Resultado de uma otimização de rota."""
    sequencia: List[RoutePoint] = field(default_factory=list)
    distancia_otimizada_km: float = 0.0
