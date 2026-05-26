#!/usr/bin/env python3
"""
Script de teste: Gera GPX com exemplo real e testa as rotas.
"""

import sys
import asyncio
from pathlib import Path

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent))

from src.exporters.gpx_builder import build_gpx
from src.exporters.parser import PosteData


async def test_gpx_generation():
    """Testa geração de GPX com dados de exemplo."""
    
    # Dados de exemplo (4 postes da Fluxosul)
    postes = [
        PosteData(
            code="1324985",
            lat=-7.530498685,
            lng=-46.062394531,
            alimentadores=["BLS01C1"],
            estruturas_mt=["N1"],
            estruturas_bt=[],
        ),
        PosteData(
            code="564283",
            lat=-7.52946995,
            lng=-46.061440421,
            alimentadores=["BLS01C1"],
            estruturas_mt=["N1", "N3"],
            estruturas_bt=["S4I"],
        ),
        PosteData(
            code="564890",
            lat=-7.53027203,
            lng=-46.062620552,
            alimentadores=["BLS01C1"],
            estruturas_mt=["N4", "N3"],
            estruturas_bt=["S3I"],
        ),
        PosteData(
            code="564891",
            lat=-7.530635006,
            lng=-46.063022235,
            alimentadores=["BLS01C1"],
            estruturas_mt=["N4"],
            estruturas_bt=[],
        ),
    ]
    
    batch_id = "019e51f2-0646-7caf-86d9-6b23494111ea"
    
    print("=" * 70)
    print("🧪 TESTE: Geração de GPX com Rotas Automáticas")
    print("=" * 70)
    
    # Teste 1: GPX SEM otimização (ordem natural)
    print("\n📌 Teste 1: GPX sem otimização (ordem natural)")
    gpx_natural = build_gpx(postes, batch_id, ordem=None)
    print(f"   ✅ Gerado ({len(gpx_natural)} bytes)")
    
    has_rte = "<rte>" in gpx_natural
    has_rtept = "<rtept" in gpx_natural
    print(f"   {'✅' if has_rte else '❌'} Contém <rte>: {has_rte}")
    print(f"   {'✅' if has_rtept else '❌'} Contém <rtept>: {has_rtept}")
    
    # Salva arquivo
    output_path = Path("tests/output/postes_TESTE_natural.gpx")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(gpx_natural)
    print(f"   📄 Salvo: {output_path}")
    
    # Teste 2: GPX COM otimização (ordem customizada)
    print("\n📌 Teste 2: GPX com otimização (ordem customizada)")
    ordem_otimizada = ["1324985", "564283", "564890", "564891"]  # ordem TSP simulada
    gpx_otimizado = build_gpx(postes, batch_id, ordem=ordem_otimizada)
    print(f"   ✅ Gerado ({len(gpx_otimizado)} bytes)")
    
    has_rte = "<rte>" in gpx_otimizado
    has_rtept = "<rtept" in gpx_otimizado
    has_optimized = "optimized>true" in gpx_otimizado
    print(f"   {'✅' if has_rte else '❌'} Contém <rte>: {has_rte}")
    print(f"   {'✅' if has_rtept else '❌'} Contém <rtept>: {has_rtept}")
    print(f"   {'✅' if has_optimized else '❌'} Marcado como otimizado: {has_optimized}")
    
    # Salva arquivo
    output_path = Path("tests/output/postes_TESTE_otimizado.gpx")
    output_path.write_text(gpx_otimizado)
    print(f"   📄 Salvo: {output_path}")
    
    # Teste 3: GPX COM geometria OSRM
    print("\n📌 Teste 3: GPX com geometria OSRM (track)")
    geometria_simulada = [
        (-7.530498685, -46.062394531),
        (-7.530400, -46.062300),
        (-7.529470, -46.061440),
        (-7.530272, -46.062621),
        (-7.530635, -46.063022),
    ]
    gpx_com_track = build_gpx(
        postes, batch_id,
        ordem=ordem_otimizada,
        route_geometry=geometria_simulada
    )
    print(f"   ✅ Gerado ({len(gpx_com_track)} bytes)")
    
    has_rte = "<rte>" in gpx_com_track
    has_trk = "<trk>" in gpx_com_track
    has_trkpt = "<trkpt" in gpx_com_track
    print(f"   {'✅' if has_rte else '❌'} Contém <rte>: {has_rte}")
    print(f"   {'✅' if has_trk else '❌'} Contém <trk>: {has_trk}")
    print(f"   {'✅' if has_trkpt else '❌'} Contém <trkpt>: {has_trkpt} ({len(geometria_simulada)} pontos)")
    
    # Salva arquivo
    output_path = Path("tests/output/postes_TESTE_com_track.gpx")
    output_path.write_text(gpx_com_track)
    print(f"   📄 Salvo: {output_path}")
    
    # Resumo
    print("\n" + "=" * 70)
    print("📊 RESUMO")
    print("=" * 70)
    print(f"""
✅ Todos os testes completados!

Arquivos gerados:
  1️⃣  postes_TESTE_natural.gpx      - GPX sem otimização
  2️⃣  postes_TESTE_otimizado.gpx    - GPX com ordem otimizada
  3️⃣  postes_TESTE_com_track.gpx    - GPX com track (geometria real)

🎯 Próximos passos:
  1. Copie um dos arquivos para seu smartphone/tablet
  2. Abra no OsmAnd
  3. Clique em "Navegar" ou "Rota"
  4. OsmAnd vai navegar pelas paradas automaticamente!
  
💡 Dica: Use o arquivo (3) para ter a linha da rota desenhada no mapa.
""")


if __name__ == "__main__":
    asyncio.run(test_gpx_generation())
