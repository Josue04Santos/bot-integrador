"""
RouteOptimizer (µ9) — Otimização de rotas via OR-Tools (TSP).

Resolve o problema do caixeiro viajante para sequências de postes/pontos,
minimizando distância total. Usa Haversine como métrica geodésica.
"""
from __future__ import annotations

import math
from typing import List

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from src.services.route_models import RoutePoint, RouteResult


# ─────────────────────────────────────────────────────────────
# FUNÇÃO PÚBLICA — Haversine
# ─────────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Distância em km entre dois pontos geográficos (fórmula de Haversine).
    Raio médio da Terra: 6371 km.
    """
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ─────────────────────────────────────────────────────────────
# CLASSE PRINCIPAL — RouteOptimizer
# ─────────────────────────────────────────────────────────────

class RouteOptimizer:
    """
    Otimizador TSP usando OR-Tools.

    Estratégia:
      - Constrói matriz de distâncias (Haversine, em metros como int).
      - Resolve com PATH_CHEAPEST_ARC + GUIDED_LOCAL_SEARCH.
      - Retorna sequência otimizada + distância total.
    """

    # Escala para converter km→int (OR-Tools exige inteiros)
    SCALE = 1000  # 1 unidade = 1 metro

    def __init__(self, deposito: RoutePoint, pontos: List[RoutePoint]):
        if not pontos:
            raise ValueError("É necessário pelo menos 1 ponto além do depósito.")
        self.deposito = deposito
        self.pontos = pontos
        # Lista completa: depósito sempre no índice 0
        self._all_points: List[RoutePoint] = [deposito] + pontos

    # ─────────────────────────────────────────────────────────
    def _build_distance_matrix(self) -> List[List[int]]:
        """Matriz N×N de distâncias em metros (int)."""
        n = len(self._all_points)
        matrix = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                a, b = self._all_points[i], self._all_points[j]
                matrix[i][j] = int(haversine_km(a.lat, a.lon, b.lat, b.lon) * self.SCALE)
        return matrix

    # ─────────────────────────────────────────────────────────
    def solve(self, time_limit_seconds: int = 5) -> RouteResult:
        """
        Resolve o TSP e retorna RouteResult com:
          - sequencia: List[RoutePoint] na ordem otimizada (sem depósito)
          - distancia_otimizada_km: float
        """
        matrix = self._build_distance_matrix()
        n = len(matrix)

        manager = pywrapcp.RoutingIndexManager(n, 1, 0)  # 1 veículo, depósito = índice 0
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return matrix[from_node][to_node]

        transit_idx = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

        params = pywrapcp.DefaultRoutingSearchParameters()
        params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        params.time_limit.seconds = time_limit_seconds

        solution = routing.SolveWithParameters(params)
        if solution is None:
            raise RuntimeError("OR-Tools não encontrou solução para o TSP.")

        # Extrai sequência
        sequencia: List[RoutePoint] = []
        index = routing.Start(0)
        total_meters = 0
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != 0:  # ignora depósito na lista de saída
                sequencia.append(self._all_points[node])
            next_index = solution.Value(routing.NextVar(index))
            total_meters += routing.GetArcCostForVehicle(index, next_index, 0)
            index = next_index

        return RouteResult(
            sequencia=sequencia,
            distancia_otimizada_km=total_meters / self.SCALE,
        )
