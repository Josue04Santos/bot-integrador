#!/usr/bin/env python3
"""
Teste de validação: GPX de equipamentos com dados reais do lote #019e54ae
"""

from src.exporters.gpx_equipamentos import build_gpx_equipamentos
from src.exporters.parser_equipamento import EquipamentoData
from datetime import datetime

# Dados do lote #019e54ae (do CSV anexado)
equipamentos = [
    EquipamentoData(
        code="1262963",
        instalacao="1262963",
        tipo="",
        poste_referencia="1325074",
        alimentador="SRM-09F2",
        perimetro="RURAL",
        potencia="112,50kVA",
        tensao_primaria="34500 Volts",
        tensao_secundaria="220Volts",
        fase="ABC",
        clientes=296,
        total_clientes_montante=0,
        total_trafos_montante=0,
        situacao="OPERACAO",
        lat=-7.105434371,
        lng=-45.645722271,
        parse_error=None,
    ),
    EquipamentoData(
        code="2020202",
        instalacao="2020202",
        tipo="Chave Fusível",
        poste_referencia="817483",
        alimentador="IPA-01C9",
        perimetro="RURAL",
        potencia="Não Informada",
        tensao_primaria="13800 Volts",
        tensao_secundaria=None,
        fase="AB",
        clientes=2,
        total_clientes_montante=0,
        total_trafos_montante=0,
        situacao="OPERACAO",
        lat=-5.533004312,
        lng=-47.375502154,
        parse_error=None,
    ),
    EquipamentoData(
        code="025617X",
        instalacao=None,
        tipo="Chave Fusível",
        poste_referencia="817681",
        alimentador="IPA-01C9",
        perimetro="RURAL",
        potencia="Não Informada",
        tensao_primaria="13800 Volts",
        tensao_secundaria=None,
        fase="ABC",
        clientes=25,
        total_clientes_montante=0,
        total_trafos_montante=0,
        situacao="OPERACAO",
        lat=-5.52476664900001,
        lng=-47.376526495,
        parse_error=None,
    ),
    EquipamentoData(
        code="3301095",
        instalacao="3301095",
        tipo="",
        poste_referencia="03052205",
        alimentador="IPA-01C9",
        perimetro="URBANO",
        potencia="Não Informada",
        tensao_primaria="13800 Volts",
        tensao_secundaria=None,
        fase="ABC",
        clientes=104,
        total_clientes_montante=0,
        total_trafos_montante=0,
        situacao="OPERACAO",
        lat=-5.52631567200001,
        lng=-47.3808438560,
        parse_error=None,
    ),
]

# Testa geração
batch_id = "019e54ae-test"
gpx_xml = build_gpx_equipamentos(equipamentos, batch_id)

# Salva em arquivo
output_file = "output/test_gpx_equipamentos_019e54ae.gpx"
with open(output_file, "w", encoding="utf-8") as f:
    f.write(gpx_xml)

print(f"✅ GPX gerado: {output_file}")
print(f"📊 Equipamentos: {len(equipamentos)}")
print(f"📏 Tamanho: {len(gpx_xml)} bytes")

# Valida estrutura
assert '<?xml version="1.0" encoding="UTF-8"?>' in gpx_xml
assert "<gpx" in gpx_xml and "</gpx>" in gpx_xml
assert "<wpt" in gpx_xml
assert "1262963" in gpx_xml
assert "2020202" in gpx_xml
assert "025617X" in gpx_xml
assert "3301095" in gpx_xml
assert "Chave Fusível" in gpx_xml

print("\n✅ Todas as validações passaram!")
print("\n📋 Primeiros 500 caracteres do GPX:")
print(gpx_xml[:500])
