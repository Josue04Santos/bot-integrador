#!/usr/bin/env python3
"""
Script de teste: Verifica se GPX contém rotas automáticas (<rte> e <trk>).

Uso:
    python test_gpx_routes.py tests/output/seu_arquivo.gpx
    
Valida:
    ✅ <rte> (route) com pontos navegáveis
    ✅ <rtept> (route points) numerados
    ✅ <trk> (track) com geometria
    ✅ <wpt> (waypoints) com ícones OsmAnd
    ✅ Metadados de rota e perfil
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def remove_namespace(tag: str) -> str:
    """Remove namespace do tag XML."""
    return tag.split('}')[-1] if '}' in tag else tag


def check_gpx_routes(gpx_path: str) -> None:
    """Analisa arquivo GPX e verifica estrutura de rotas."""
    file_path = Path(gpx_path)
    
    if not file_path.exists():
        print(f"❌ Arquivo não encontrado: {gpx_path}")
        sys.exit(1)
    
    print(f"\n📂 Analisando: {file_path.name}\n")
    print("=" * 70)
    
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"❌ Erro ao parsear XML: {e}")
        sys.exit(1)
    
    # 1. Metadados
    metadata = root.find('.//{http://www.topografix.com/GPX/1/1}metadata')
    if metadata is not None:
        name_elem = metadata.find('{http://www.topografix.com/GPX/1/1}name')
        desc_elem = metadata.find('{http://www.topografix.com/GPX/1/1}desc')
        name = name_elem.text if name_elem is not None else "N/A"
        desc = desc_elem.text if desc_elem is not None else "N/A"
        print(f"📋 Metadados:")
        print(f"   Nome: {name}")
        print(f"   Desc: {desc}\n")
    
    # 2. Waypoints
    wpts = root.findall('.//{http://www.topografix.com/GPX/1/1}wpt')
    print(f"📍 Waypoints (marcadores): {len(wpts)}")
    if wpts:
        print(f"   Primeiros 3:")
        for wpt in wpts[:3]:
            name_elem = wpt.find('{http://www.topografix.com/GPX/1/1}name')
            name = name_elem.text if name_elem is not None else "N/A"
            lat = wpt.get('lat')
            lon = wpt.get('lon')
            print(f"     • {name} ({lat}, {lon})")
    print()
    
    # 3. Routes (CRÍTICO para OsmAnd)
    routes = root.findall('.//{http://www.topografix.com/GPX/1/1}rte')
    print(f"🚗 Routes (<rte>): {len(routes)}")
    if routes:
        for i, rte in enumerate(routes, 1):
            name_elem = rte.find('{http://www.topografix.com/GPX/1/1}name')
            desc_elem = rte.find('{http://www.topografix.com/GPX/1/1}desc')
            name = name_elem.text if name_elem is not None else "N/A"
            desc = desc_elem.text if desc_elem is not None else "N/A"
            rtepts = rte.findall('{http://www.topografix.com/GPX/1/1}rtept')
            print(f"\n   Rota {i}: {name}")
            print(f"   Desc: {desc}")
            print(f"   Pontos de rota: {len(rtepts)}")
            if rtepts:
                print(f"   Primeiros/últimos 2:")
                for pt in rtepts[:1]:
                    pt_name_elem = pt.find('{http://www.topografix.com/GPX/1/1}name')
                    pt_type_elem = pt.find('{http://www.topografix.com/GPX/1/1}type')
                    pt_name = pt_name_elem.text if pt_name_elem is not None else "N/A"
                    pt_type = pt_type_elem.text if pt_type_elem is not None else "N/A"
                    print(f"     • {pt_name} (tipo: {pt_type})")
                if len(rtepts) > 1:
                    pt = rtepts[-1]
                    pt_name_elem = pt.find('{http://www.topografix.com/GPX/1/1}name')
                    pt_type_elem = pt.find('{http://www.topografix.com/GPX/1/1}type')
                    pt_name = pt_name_elem.text if pt_name_elem is not None else "N/A"
                    pt_type = pt_type_elem.text if pt_type_elem is not None else "N/A"
                    print(f"     • {pt_name} (tipo: {pt_type})")
    else:
        print("   ⚠️  NENHUMA ROTA ENCONTRADA!")
        print("   ⚠️  O OsmAnd não vai navigar automaticamente!")
    print()
    
    # 4. Tracks (geometria rodoviária)
    tracks = root.findall('.//{http://www.topografix.com/GPX/1/1}trk')
    print(f"🛣️  Tracks (<trk>): {len(tracks)}")
    if tracks:
        for i, trk in enumerate(tracks, 1):
            name_elem = trk.find('{http://www.topografix.com/GPX/1/1}name')
            name = name_elem.text if name_elem is not None else "N/A"
            trkpts = trk.findall('.//{http://www.topografix.com/GPX/1/1}trkpt')
            print(f"\n   Track {i}: {name}")
            print(f"   Pontos de geometria: {len(trkpts)}")
    else:
        print("   ℹ️  Sem track (OK se tiver <rte>)")
    print()
    
    # 5. Extensões OsmAnd
    extensions = root.findall('.//{https://osmand.net}*')
    print(f"🔧 Extensões OsmAnd: {len(extensions)}")
    if extensions:
        ext_types = {}
        for ext in extensions:
            tag = remove_namespace(ext.tag)
            text = ext.text or "[vazio]"
            if tag not in ext_types:
                ext_types[tag] = text
        for tag in sorted(ext_types.keys())[:10]:  # Limita a 10 primeiras
            print(f"   • {tag}: {ext_types[tag]}")
    print()
    
    # 6. Validação Final
    print("=" * 70)
    print("✅ VERIFICAÇÃO FINAL:\n")
    
    has_wpts = len(wpts) > 0
    has_routes = len(routes) > 0
    has_rtepts = sum(len(r.findall('{http://www.topografix.com/GPX/1/1}rtept')) for r in routes) > 0
    
    checks = [
        ("Tem <wpt> (waypoints)", has_wpts, "✅"),
        ("Tem <rte> (routes)", has_routes, "✅" if has_routes else "❌ CRÍTICO!"),
        ("Route tem <rtept> points", has_rtepts, "✅" if has_rtepts else "❌ CRÍTICO!"),
    ]
    
    for label, status, icon in checks:
        print(f"{icon} {label}: {'SIM' if status else 'NÃO'}")
    
    print("\n" + "=" * 70)
    
    if has_routes and has_rtepts:
        print("\n🎉 GPX ESTÁ PRONTO PARA OSMAND!")
        print("   1. Abra o OsmAnd")
        print(f"   2. Importe o arquivo: {file_path.name}")
        print("   3. Clique em 'Navegar' para iniciar a rota automática")
        print("   4. O OsmAnd vai parar em cada ponto <rtept>")
    else:
        print("\n⚠️  PROBLEMA: GPX falta elementos de rota!")
        print("   Regenere o arquivo com a versão corrigida.")
    
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("Uso: python test_gpx_routes.py <arquivo.gpx>")
        sys.exit(1)
    
    check_gpx_routes(sys.argv[1])
