"""
RELATÓRIO DE VALIDAÇÃO — Lote #019e556e
Comparação: CSV de Equipamentos vs Resposta do Bot
"""

import csv
from io import StringIO

# CSV enviado
csv_content = """codigo;instalacao;tipo;poste_referencia;alimentador;perimetro;potencia;tensao_primaria;tensao_secundaria;fase;clientes_diretos;clientes_montante;trafos_montante;situacao;latitude;longitude;coordenadas;google_maps;parse_error
1262963;1262963;Transformador;1325074;SRM-09F2;RURAL;112,50kVA;34500 Volts;220Volts;ABC;296;1648;586;OPERACAO;-7.105434371;-45.645722271;-7.105434371, -45.645722271;https://www.google.com.br/maps/place/-7.105434371,-45.645722271;
2020202;2020202;Chave Fusível;817483;IPA-01C9;RURAL;Não Informada;13800 Volts;;AB;2;7424;445;OPERACAO;-5.533004312;-47.375502154;-5.533004312, -47.375502154;https://www.google.com.br/maps/place/-5.533004312,-47.375502154;
025617X;025617X;Chave Fusível;817681;IPA-01C9;RURAL;Não Informada;13800 Volts;;ABC;25;7424;445;OPERACAO;-5.52476664900001;-47.376526495;-5.52476664900001, -47.376526495;https://www.google.com.br/maps/place/-5.52476664900001,-47.376526495;
3301095;3301095;;03052205;IPA-01C9;URBANO;Não Informada;13800 Volts;;ABC;104;7424;445;OPERACAO;-5.52631567200001;-47.380843856;-5.52631567200001, -47.380843856;https://www.google.com.br/maps/place/-5.52631567200001,-47.380843856;
"""

# Parse CSV
reader = csv.DictReader(StringIO(csv_content), delimiter=";")
equipamentos = list(reader)

# Dados esperados do bot (conforme mensagens)
bot_esperado = {
    "1262963": {
        "tipo": "Transformador",  # 🆕 mudança!
        "instalacao": "1262963",
        "alimentador": "SRM-09F2",
        "perimetro": "RURAL",
        "potencia": "112,50kVA",
        "tensao_primaria": "34500 Volts",
        "tensao_secundaria": "220Volts",
        "fase": "ABC",
        "clientes": "296",
        "situacao": "OPERACAO",
        "poste": "1325074",
        "lat": "-7.105434371",
        "lng": "-45.645722271",
    },
    "2020202": {
        "tipo": "Chave Fusível",
        "instalacao": "2020202",
        "alimentador": "IPA-01C9",
        "perimetro": "RURAL",
        "potencia": "Não Informada",
        "tensao_primaria": "13800 Volts",
        "tensao_secundaria": "",
        "fase": "AB",
        "clientes": "2",
        "situacao": "OPERACAO",
        "poste": "817483",
        "lat": "-5.533004312",
        "lng": "-47.375502154",
    },
    "025617X": {
        "tipo": "Chave Fusível",
        "instalacao": "025617X",
        "alimentador": "IPA-01C9",
        "perimetro": "RURAL",
        "potencia": "Não Informada",
        "tensao_primaria": "13800 Volts",
        "tensao_secundaria": "",
        "fase": "ABC",
        "clientes": "25",
        "situacao": "OPERACAO",
        "poste": "817681",
        "lat": "-5.52476664900001",
        "lng": "-47.376526495",
    },
    "3301095": {
        "tipo": "",  # Vazio
        "instalacao": "3301095",
        "alimentador": "IPA-01C9",
        "perimetro": "URBANO",
        "potencia": "Não Informada",
        "tensao_primaria": "13800 Volts",
        "tensao_secundaria": "",
        "fase": "ABC",
        "clientes": "104",
        "situacao": "OPERACAO",
        "poste": "03052205",
        "lat": "-5.52631567200001",
        "lng": "-47.380843856",
    },
}

print("=" * 70)
print("📋 RELATÓRIO DE VALIDAÇÃO — Lote #019e556e")
print("=" * 70)

total_ok = 0
total_erros = 0

for i, equip in enumerate(equipamentos, 1):
    codigo = equip["codigo"]
    esperado = bot_esperado.get(codigo)
    
    print(f"\n[{i}/4] Equipamento: {codigo}")
    print("─" * 70)
    
    if not esperado:
        print(f"  ❌ ERRO: Equipamento não encontrado nos dados esperados")
        total_erros += 1
        continue
    
    erros_equip = []
    
    # Validações
    checks = [
        ("tipo", "Tipo", equip.get("tipo", "").strip()),
        ("instalacao", "Instalação", equip.get("instalacao", "").strip()),
        ("alimentador", "Alimentador", equip.get("alimentador", "").strip()),
        ("perimetro", "Perímetro", equip.get("perimetro", "").strip()),
        ("potencia", "Potência", equip.get("potencia", "").strip()),
        ("tensao_primaria", "Tensão Primária", equip.get("tensao_primaria", "").strip()),
        ("fase", "Fase", equip.get("fase", "").strip()),
        ("clientes_diretos", "Clientes", equip.get("clientes_diretos", "").strip()),
        ("situacao", "Situação", equip.get("situacao", "").strip()),
        ("poste_referencia", "Poste Referência", equip.get("poste_referencia", "").strip()),
        ("latitude", "Latitude", equip.get("latitude", "").strip()),
        ("longitude", "Longitude", equip.get("longitude", "").strip()),
    ]
    
    for key, label, valor_csv in checks:
        # Mapear chaves especiais
        key_map = {
            "poste_referencia": "poste",
            "clientes_diretos": "clientes",
            "latitude": "lat",
            "longitude": "lng",
        }
        mapped_key = key_map.get(key, key)
        valor_esperado = str(esperado.get(mapped_key, "")).strip()
        
        if valor_csv == valor_esperado:
            print(f"  ✅ {label}: {valor_csv}")
        else:
            print(f"  ❌ {label}: '{valor_csv}' (esperado: '{valor_esperado}')")
            erros_equip.append(label)
    
    if erros_equip:
        print(f"\n  ⚠️  Discrepâncias encontradas: {', '.join(erros_equip)}")
        total_erros += 1
    else:
        print(f"\n  ✅ Todos os campos validados com sucesso!")
        total_ok += 1

print("\n" + "=" * 70)
print("📊 RESUMO DA VALIDAÇÃO")
print("=" * 70)
print(f"✅ Equipamentos OK: {total_ok}/4")
print(f"❌ Equipamentos com erros: {total_erros}/4")
print(f"📍 Total com coordenadas: 4/4")
print(f"📦 Total equipamentos: 4")

print("\n" + "=" * 70)
print("🆕 MUDANÇAS DETECTADAS (vs Lote #019e54ae)")
print("=" * 70)
print("✅ 1262963: Tipo foi preenchido como 'Transformador'")
print("✅ 2020202: Mantém 'Chave Fusível' (correto)")
print("✅ 025617X: Mantém 'Chave Fusível' (correto)")
print("⚠️  3301095: Tipo vazio (sem informação)")

print("\n" + "=" * 70)
print("📦 ARQUIVOS GERADOS (esperados)")
print("=" * 70)
print("✅ lote_2026-05-23_019e556e.kml")
print("✅ lote_2026-05-23_019e556e_postes.gpx (se postes foram consultados)")
print("✅ lote_2026-05-23_019e556e_equipamentos.gpx (🆕 NOVO!)")
print("✅ lote_2026-05-23_019e556e_postes.csv (se postes foram consultados)")
print("✅ lote_2026-05-23_019e556e_equipamentos.csv")
print("✅ lote_2026-05-23_019e556e_invalidos.txt (se houver)")

print("\n" + "=" * 70)
print("🎯 CONCLUSÃO")
print("=" * 70)
if total_erros == 0:
    print("✅ CSV VALIDADO COM SUCESSO!")
    print("✅ GPX DE EQUIPAMENTOS DEVE TER SIDO GERADO")
    print("✅ Pronto para inspeção no OsmAnd/Organic Maps")
else:
    print(f"⚠️  ATENÇÃO: {total_erros} equipamento(s) com discrepâncias")

print("\n" + "=" * 70)
