"""
Testes do RouteOptimizer (µ9).
Cenários reais com coordenadas de Imperatriz/MA.
"""
import pytest
from src.services.route_models import RoutePoint
from src.services.route_optimizer import RouteOptimizer, haversine_km


# ─────────────────────────────────────────────────────────────
# FIXTURES — Pontos reais de Imperatriz/MA
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def deposito_imperatriz():
    """Depósito fictício no centro de Imperatriz."""
    return RoutePoint(id="DEP", lat=-5.5260, lon=-47.4915, label="Depósito Central")


@pytest.fixture
def postes_imperatriz():
    """6 postes espalhados por Imperatriz (bairros diversos)."""
    return [
        RoutePoint(id="P1", lat=-5.5180, lon=-47.4820, label="Maranhão Novo"),
        RoutePoint(id="P2", lat=-5.5340, lon=-47.4780, label="Bacuri"),
        RoutePoint(id="P3", lat=-5.5210, lon=-47.4950, label="Centro"),
        RoutePoint(id="P4", lat=-5.5420, lon=-47.4880, label="Vila Nova"),
        RoutePoint(id="P5", lat=-5.5150, lon=-47.4890, label="Beira-Rio"),
        RoutePoint(id="P6", lat=-5.5380, lon=-47.5020, label="Parque do Buriti"),
    ]


# ─────────────────────────────────────────────────────────────
# TESTES — Haversine
# ─────────────────────────────────────────────────────────────

def test_haversine_zero_quando_mesmo_ponto():
    assert haversine_km(-5.52, -47.49, -5.52, -47.49) == pytest.approx(0.0, abs=0.001)


def test_haversine_imperatriz_aproximado():
    # Centro de Imperatriz → Aeroporto Renato Moreira (~3-5 km)
    d = haversine_km(-5.5260, -47.4915, -5.5314, -47.4600)
    assert 2.5 < d < 5.0, f"Distância inesperada: {d} km"


# ─────────────────────────────────────────────────────────────
# TESTES — RouteOptimizer
# ─────────────────────────────────────────────────────────────

def test_otimizacao_minima_2_pontos(deposito_imperatriz):
    p1 = RoutePoint(id="A", lat=-5.5180, lon=-47.4820, label="A")
    opt = RouteOptimizer(deposito=deposito_imperatriz, pontos=[p1])
    resultado = opt.solve()
    assert len(resultado.sequencia) == 1
    assert resultado.sequencia[0].id == "A"
    assert resultado.distancia_otimizada_km > 0


def test_otimizacao_6_pontos_imperatriz(deposito_imperatriz, postes_imperatriz):
    opt = RouteOptimizer(deposito=deposito_imperatriz, pontos=postes_imperatriz)
    resultado = opt.solve()

    # Calcula distância "natural" (ordem original)
    natural_km = 0.0
    anterior = deposito_imperatriz
    for p in postes_imperatriz:
        natural_km += haversine_km(anterior.lat, anterior.lon, p.lat, p.lon)
        anterior = p
    natural_km += haversine_km(anterior.lat, anterior.lon, deposito_imperatriz.lat, deposito_imperatriz.lon)

    economia_pct = (1 - resultado.distancia_otimizada_km / natural_km) * 100
    seq_labels = " → ".join(p.id for p in resultado.sequencia)

    print(f"\n📊 Natural:    {natural_km:.2f} km")
    print(f"📊 Otimizada:  {resultado.distancia_otimizada_km:.2f} km")
    print(f"📊 Economia:   {economia_pct:.1f}%")
    print(f"📊 Sequência:  {seq_labels}")

    assert len(resultado.sequencia) == 6
    assert resultado.distancia_otimizada_km <= natural_km
    # Todos os IDs originais devem estar presentes
    assert {p.id for p in resultado.sequencia} == {p.id for p in postes_imperatriz}


def test_erro_com_menos_de_2_pontos(deposito_imperatriz):
    with pytest.raises(ValueError, match="pelo menos 1 ponto"):
        RouteOptimizer(deposito=deposito_imperatriz, pontos=[])


def test_latitude_invalida():
    with pytest.raises(ValueError):
        RoutePoint(id="X", lat=-95.0, lon=-47.0, label="Invalido")
