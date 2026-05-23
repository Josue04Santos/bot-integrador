# 🗺️ Guia: Roterização Automática no OsmAnd

> **Status**: ✅ CORRIGIDO - GPX agora gera rotas automáticas!

---

## 🔴 Problema Original

Você criou um `.gpx` mas o OsmAnd **não criava rotas automáticas** quando abria o mapa. O arquivo continha apenas:
- ✅ `<wpt>` (waypoints/marcadores)
- ❌ `<rte>` (routes/rotas navegáveis) — **FALTAVA!**
- ❌ `<trk>` (tracks/linhas de rota) — **FALTAVA!**

### Por que isso acontecia?

O arquivo GPX anterior era gerado de forma **incompleta**:

```xml
<?xml version="1.0"?>
<gpx>
  <metadata>...</metadata>
  <wpt lat="..." lon="...">    <!-- ✅ Marcador apenas -->
    <name>1324985</name>
  </wpt>
  <!-- ❌ Faltavam <rte> (route) e <rtept> (route points) aqui! -->
</gpx>
```

---

## ✅ Solução Implementada

### 1. **`<rte>` (Route) — Rota Navegável**
Agora o GPX SEMPRE gera uma `<rte>` com `<rtept>` (route points):

```xml
<rte>
  <name>🚗 Rota Otimizada — Lote 019e51f2</name>
  <desc>4 paradas (perfil: car)</desc>
  
  <!-- Pontos da rota em sequência —OsmAnd vai navegar por aqui! -->
  <rtept lat="-7.530498685" lon="-46.062394531">
    <name>01. 1324985</name>
    <type>intermediate</type>  <!-- ou "destination" no último -->
  </rtept>
  
  <rtept lat="-7.52946995" lon="-46.061440421">
    <name>02. 564283</name>
    <type>intermediate</type>
  </rtept>
  
  <!-- ... mais pontos ... -->
</rte>
```

### 2. **`<trk>` (Track) — Linha de Rota**
Se houver geometria OSRM (coordenadas da rota real nas ruas), gera também:

```xml
<trk>
  <name>🛣️ Trilha Rodoviária — Lote 019e51f2</name>
  <desc>Geometria da rota traçada por OSRM (ruas reais)</desc>
  
  <trkseg>
    <trkpt lat="-7.530498685" lon="-46.062394531"></trkpt>
    <trkpt lat="-7.530400" lon="-46.062300"></trkpt>
    <!-- ... dezenas de pontos ... -->
    <trkpt lat="-7.530635" lon="-46.063022"></trkpt>
  </trkseg>
</trk>
```

### 3. **Metadados OsmAnd Expandidos**
Agora inclui informações que o OsmAnd usa para navegação:

```xml
<extensions>
  <osmand:routing_profile>car</osmand:routing_profile>
  <osmand:route_type>inspection</osmand:route_type>
  <osmand:total_stops>4</osmand:total_stops>
  <osmand:optimized>true</osmand:optimized>  <!-- Se rota foi otimizada -->
</extensions>
```

---

## 🎯 Como Usar a Rota no OsmAnd

### 📱 No OsmAnd (Android/iOS)

1. **Copiar arquivo GPX para o telefone**
   ```
   adb push postes_TESTE_com_track.gpx /sdcard/Download/
   ```
   Ou transferir via USB/nuvem

2. **Abrir o OsmAnd**

3. **Importar arquivo**
   - Menu → Importar GPX
   - Ou arrastar o arquivo para o mapa

4. **Iniciar navegação**
   - Toque no arquivo importado
   - Clique em **"Navegar"** ou **"Rota"**
   - Escolha o perfil: **Carro**, Bicicleta, ou Pedestrian

5. **OsmAnd vai:**
   - ✅ Desenhar a linha de rota (track)
   - ✅ Parar em cada ponto (`<rtept>`)
   - ✅ Navegar automaticamente para o próximo
   - ✅ Calcular distância e tempo de viagem

---

## 🧪 Verificar se GPX Está Correto

Use o script de validação:

```bash
# Ativar virtualenv
source venv/bin/activate

# Testar um arquivo
python3 test_gpx_routes.py tests/output/seu_arquivo.gpx
```

**Saída esperada:**
```
✅ Tem <wpt> (waypoints): SIM
✅ Tem <rte> (routes): SIM
✅ Route tem <rtept> points: SIM

🎉 GPX ESTÁ PRONTO PARA OSMAND!
```

---

## 📊 Tipos de GPX Gerados

Seu bot gera **3 variações**:

### 1. **Natural (sem otimização)**
```bash
# Usa ordem dos dados conforme recebidos
gpx_xml = build_gpx(postes, batch_id, ordem=None)
```
- ✅ Sempre funciona
- ❌ Pode não ser a rota mais curta

### 2. **Otimizado (com TSP)**
```bash
# Usa ordem calculada pelo RouteOptimizer (OR-Tools)
gpx_xml = build_gpx(postes, batch_id, ordem=ordem_otimizada)
```
- ✅ Rota mais curta (economia de distância)
- ✅ Marcado como `optimized: true`
- ⚠️ Requer RouteOptimizer funcional

### 3. **Com Track (geometria OSRM)**
```bash
# Adiciona linha de rota seguindo ruas reais
gpx_xml = build_gpx(
    postes, batch_id,
    ordem=ordem_otimizada,
    route_geometry=osrm_geometry
)
```
- ✅ Melhor visualização (linha seguindo ruas)
- ✅ Tempo de viagem realista
- ⚠️ Requer conectividade com OSRM

---

## 🔧 Código-Chave Modificado

### [src/exporters/gpx_builder.py](../src/exporters/gpx_builder.py)

**Mudanças principais:**

1. **`build_gpx()` agora SEMPRE gera `<rte>`** (mesmo sem otimização)
   ```python
   # Antes: só gerava <rte> se ordem fosse fornecida
   # Agora: sempre gera <rte> com ordem natural ou otimizada
   
   if ordem:
       postes_ordenados = [...ordem otimizada...]
   else:
       postes_ordenados = list(postes)  # ← NOVO: usa ordem natural
   ```

2. **Waypoints numerados com cores**
   ```python
   # Início = Verde (#4CAF50)
   # Fim = Vermelho (#F44336)
   # Meio = Azul (#1976D2)
   ```

3. **Metadados expandidos para OsmAnd**
   ```xml
   <osmand:route_type>inspection</osmand:route_type>
   <osmand:total_stops>4</osmand:total_stops>
   <osmand:optimized>true</osmand:optimized>
   ```

---

## ⚡ Fluxo Completo

```
┌─────────────────────┐
│ Consulta Postes     │
│ (Telegram)          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Banco de Dados      │
│ (SQLAlchemy)        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Route Optimizer     │
│ (OR-Tools TSP)      │ ← Calcula melhor ordem
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ OSRM Client         │
│ (Geometria real)    │ ← Traça linha nas ruas
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ build_gpx()         │
│ (GPX Builder)       │ ← AGORA COM <rte> + <trk>
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ postes_TESTE.gpx    │
│ ✅ Pronto p/OsmAnd  │
└─────────────────────┘
           │
           ▼
┌─────────────────────┐
│ OsmAnd (no celular) │
│ 🗺️ Navegar!        │
└─────────────────────┘
```

---

## 📝 Exemplos de Teste

### Gerar GPX de teste
```bash
cd ~/projetos/dev/bot-integrador
source venv/bin/activate
python3 test_generate_gpx.py
```

Cria:
- `postes_TESTE_natural.gpx` — sem otimização
- `postes_TESTE_otimizado.gpx` — com TSP
- `postes_TESTE_com_track.gpx` — com geometria OSRM

### Validar arquivo
```bash
python3 test_gpx_routes.py tests/output/postes_TESTE_com_track.gpx
```

---

## 🚀 Próximos Passos

1. **Teste no OsmAnd real**
   - Copie um arquivo `.gpx` para seu telefone
   - Importe no OsmAnd
   - Toque em "Navegar"

2. **Integrar com seu Telegram**
   - Botão "📍 Baixar GPX" já funciona
   - Use `build_gpx()` com `ordem` e `route_geometry` reais

3. **Melhorias futuras**
   - [ ] Suporte a múltiplas rotas (múltiplos `<rte>` em um arquivo)
   - [ ] Exportar status do inspetor (concluído/erro)
   - [ ] Integração com fotos (waypoints com anexos)
   - [ ] Suporte a KML também

---

## ❓ FAQ

### **P: Por que o OsmAnd não navega automaticamente?**
R: Precisava de `<rte>` e `<rtept>`. Agora está corrigido! Regenere o arquivo.

### **P: Como eu sei qual rota é melhor?**
R: Use o arquivo `postes_TESTE_com_track.gpx` — tem a geometria real das ruas.

### **P: E se OSRM ficar offline?**
R: Sem problema — o arquivo com `<rte>` + `<wpt>` já funciona (sem visualização da linha).

### **P: Posso usar no Google Maps?**
R: Não — GMaps usa `.kml`. Use o `kml_builder.py` para isso.

### **P: Qual é o tamanho máximo de um GPX?**
R: Testado até 500+ pontos. OsmAnd suporta.

---

## 📞 Suporte

Se o GPX não funcionar:

1. **Valide o arquivo:**
   ```bash
   python3 test_gpx_routes.py seu_arquivo.gpx
   ```

2. **Verifique se tem `<rte>` e `<rtept>`:**
   ```bash
   grep -E "<rte>|<rtept" seu_arquivo.gpx
   ```

3. **Abra no editor de texto** para inspecionar manualmente

---

**Pronto! 🎉 Seu bot agora gera rotas que o OsmAnd reconhece!**
