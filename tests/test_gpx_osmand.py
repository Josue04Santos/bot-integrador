"""
🧪 Teste de geração de GPX otimizado para OsmAnd.

Gera um arquivo em tests/output/teste_osmand.gpx
pronto pra ser enviado pro celular e testado.

Uso:
    python -m tests.test_gpx_osmand
"""

from pathlib import Path
from src.exporters.gpx_builder import build_gpx
from src.exporters.parser import PosteData


OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def main() -> None:
    # ─── Simula postes em Imperatriz/MA ──────────────────────
    postes = [
        PosteData(
            code="P001", lat=-5.5236, lng=-47.4775,
            alimentadores=["IPZ-01"],
            estruturas_mt=["MT-A"],
            estruturas_bt=["BT-1"],
        ),
        PosteData(
            code="P002", lat=-5.5180, lng=-47.4820,
            alimentadores=["IPZ-02"],
            estruturas_mt=[],
            estruturas_bt=["BT-2"],
        ),
        PosteData(
            code="P003", lat=-5.5300, lng=-47.4700,
            alimentadores=["IPZ-01"],
            estruturas_mt=["MT-B"],
            estruturas_bt=[],
        ),
    ]

    # ─── Simula geometria OSRM (rota nas ruas) ───────────────
    geometry = [
        (-5.5236, -47.4775),
        (-5.5210, -47.4798),
        (-5.5180, -47.4820),
        (-5.5240, -47.4760),
        (-5.5300, -47.4700),
    ]

    # ─── Gera XML ────────────────────────────────────────────
    xml = build_gpx(
        postes=postes,
        batch_id="TESTE-OSMAND-001",
        ordem=["P001", "P002", "P003"],
        route_geometry=geometry,
        profile="car",
    )

    # ─── Salva ───────────────────────────────────────────────
    output_file = OUTPUT_DIR / "teste_osmand.gpx"
    output_file.write_text(xml, encoding="utf-8")

    # ─── Estatísticas ────────────────────────────────────────
    wpt_count = xml.count("<wpt ")
    rte_count = xml.count("<rtept ")
    trk_count = xml.count("<trkpt ")

    print("=" * 60)
    print("✅ GPX GERADO COM SUCESSO!")
    print("=" * 60)
    print(f"📁 Arquivo : {output_file}")
    print(f"📏 Tamanho : {len(xml):,} bytes")
    print()
    print("📊 ESTATÍSTICAS:")
    print(f"   🔵 Waypoints (marcadores) : {wpt_count}")
    print(f"   🟢 Route points (paradas) : {rte_count}")
    print(f"   🛣️  Track points (trilha) : {trk_count}")
    print()
    print("=" * 60)
    print("🔍 PRIMEIRAS 35 LINHAS DO ARQUIVO:")
    print("=" * 60)
    for line in xml.splitlines()[:35]:
        print(line)
    print("=" * 60)


if __name__ == "__main__":
    main()
