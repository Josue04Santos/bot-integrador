# API_CHI — Consulta de Componentes para Cálculo de CHI

> Documento de especificação da API de consulta usada pela equipe técnica para
> calcular o **CHI** (tempo de programação × número de clientes do componente).
> Consumidor: sistema (via "Naeg"), não o bot Telegram.

---

## 0. ⚠️ Achado crítico — verificado no Postgres de produção em 2026-07-22

Conferi direto no banco real (`192.168.1.202/bot_integrador`, via `.env`,
`DATABASE_BACKEND=postgres`), não só no código-fonte:

| Tabela | Linhas | Observação |
|---|---|---|
| `network_queries` | 994 | 444 instalações + 429 postes com `status=received` (sucesso) |
| `code_cache` | 630 | 252 poste + 378 instalação |
| `query_batches` | 144 | |
| **`meters`** | **0** | **nunca foi populada, nenhuma vez** |
| **`parsed_data`** (coluna) | **NULL em 100% das 994 linhas** | nunca foi populada |

**Ou seja: o parser (`parser.py` / `parser_equipamento.py`) existe no código,
mas seu resultado nunca é persistido de volta no banco.** O que existe de
fato, salvo, é só o `raw_response` (texto bruto do `@ReincidenciasBot`).
Confirmei que o texto contém tudo que precisamos — inclusive a tabela de
chaves a montante — só que como texto solto, não estruturado:

```
Instalação: **2020202**
Alimentador: IPA-01C9
Perímetro: RURAL
Tipo: Chave Fusível
Poste: 817483
Clientes: 2
Situação: OPERACAO
...
CHAVES A MONTANTE ATÉ A SUBESTAÇÃO
Componente   Elo   Cliente   Trafos
---------
```

Além disso, existem 2 tabelas no banco real que **não estão em `models.py`**:
`telethon_sessions` e `usuarios` — provável debito técnico/migração feita à
mão direto no Postgres, fora do fluxo SQLAlchemy/Alembic (não há
`alembic_version` no dev SQLite, sinal de que as migrations não são a fonte
única da verdade do schema).

### Impacto direto na API de CHI

As seções 3, 6 e 7 abaixo descrevem o schema **como projetado no código**.
Na prática, para a API de CHI funcionar hoje, **não dá pra só fazer
`SELECT` em `meters` ou `parsed_data`** — eles estão vazios. Duas saídas:

- **(a) Parse on-read**: a API roda `parse_equipamento_response()` /
  `parse_poste_response()` em cima do `raw_response` a cada consulta
  (cache-hit ou não), sem depender de `meters`/`parsed_data` estarem
  preenchidos.
- **(b) Backfill + passar a persistir**: criar uma migration/script que
  processa os 994 `raw_response` existentes, popula `parsed_data` e `meters`
  retroativamente, e corrige o worker para persistir o parse dali pra frente.

(a) é mais rápido pra colocar a API no ar; (b) é mais correto a longo prazo
(também beneficia KML/GPX, que hoje devem estar reparseando o raw toda vez
que exportam). Ver novo item 6.5.

---

## 1. Objetivo

A técnica precisa, para um componente (chave/equipamento — `FU`, `CF`, `RG`, `DJ`, `SE`),
obter o **número de clientes daquele componente específico** para multiplicar pelo
tempo de programação e calcular o CHI.

Fluxo esperado pelo solicitante:

1. Consulta o componente na nossa base.
2. Se já existe (cache) → retorna na hora.
3. Se **não existe** → consulta o bot externo (`@ReincidenciasBot`), salva e retorna.
4. Do lado da técnica: `CHI = tempo_programacao × clientes_do_componente`.

O cálculo do CHI em si **não é feito por nós** — só fornecemos o dado
(`clientes` por componente). O tempo de programação é informação da técnica.

---

## 2. Ponto de atenção — nível do dado

O sistema tem dois níveis de "clientes" e a API **precisa expor o nível certo**:

| Nível | Campo | Fonte | Uso |
|---|---|---|---|
| Instalação (total) | `EquipamentoData.clientes` | `parsed_data` da consulta de instalação | Não serve para o CHI — é agregado |
| **Componente (granular)** | `chaves_montante[].clientes` | tabela `meters` | ✅ É o que o CHI precisa |

Cada instalação consultada retorna uma **tabela de chaves a montante**, uma linha
por componente (`FU`, `CF`, `RG`, `DJ`, `SE`), cada uma com seu próprio `clientes`
e `trafos`. A API de CHI deve responder por **componente**, não pela instalação inteira.

---

## 3. Fonte dos dados (tabelas existentes)

> ⚠️ Schema como **projetado** — na prática `meters` e `parsed_data` estão
> vazios em produção hoje. Ver seção 0.

- **`code_cache`** — 1 linha por `(code, query_type)`, é a fonte de verdade do cache.
  TTL de 7 dias (fora disso, entrega o cache e atualiza em background).
- **`network_queries`** — histórico de cada consulta individual (auditoria).
- **`meters`** — linhas de `chaves_montante` vinculadas a uma `network_query`
  (`componente`, `code`, `elo`, `clientes`, `trafos`, `observacao`).

Nenhuma tabela nova é necessária. `meters` já tem os campos requeridos.

> Nota: `meters` hoje é populada a partir de `network_queries` (histórico), não de
> `code_cache`. Para a API responder também nos cache-hits, será preciso ou (a)
> persistir `chaves_montante` também associadas ao `code_cache`, ou (b) sempre
> resolver o componente pela consulta mais recente em `network_queries` do código
> pai (instalação). Decidir isso é um dos itens em aberto (seção 6).

---

## 4. Endpoint proposto

```
GET /api/v1/chi/componente/{codigo}
```

Onde `{codigo}` é o código do **componente** (ex.: `FU1234`) ou, alternativamente,
o código da **instalação** + filtro por componente — a definir (ver seção 6).

### Query params

| Param | Obrigatório | Descrição |
|---|---|---|
| `tipo` | não (default `instalacao`) | `poste` \| `instalacao` |
| `forcar_atualizacao` | não (default `false`) | ignora cache e consulta o bot externo |

### Headers

```
X-API-Key: <chave da API, mesmo padrão do endpoint /api/v1/consulta já existente>
```

### Resposta (200)

```json
{
  "success": true,
  "codigo": "INST12345",
  "origem": "cache",            // "cache" | "bot_externo"
  "cache_idade_horas": 12,
  "componentes": [
    {
      "componente": "FU",
      "code": "FU001",
      "elo": "6K",
      "clientes": 42,
      "trafos": 3,
      "observacao": null
    },
    {
      "componente": "CF",
      "code": "CF002",
      "elo": "10K",
      "clientes": 118,
      "trafos": 7,
      "observacao": null
    }
  ]
}
```

### Resposta — componente não encontrado (404)

```json
{
  "success": false,
  "codigo": "INST99999",
  "erro": "Componente não encontrado (consultado ao vivo, sem retorno do bot externo)"
}
```

### Erros

| Status | Motivo |
|---|---|
| 400 | `tipo` inválido |
| 401 | API key inválida/ausente |
| 404 | código não encontrado (nem em cache, nem no bot externo) |
| 504 | timeout na consulta ao bot externo |

---

## 5. Comportamento cache-first (reaproveita lógica existente)

Reaproveitar a mesma regra do bot (README, seção "Cache Inteligente"):

- Código no cache e fresco (< 7 dias) → responde imediato, `origem: "cache"`.
- Código no cache mas vencido → responde imediato do cache **e** dispara
  atualização em background (não bloqueia a resposta da API).
- Código novo → consulta o bot externo de forma síncrona (respeitando o lock
  que já existe entre worker em tempo real e auto-refresh), salva e responde,
  `origem: "bot_externo"`.

Isso é diferente do endpoint `/api/v1/consulta` que já existe hoje em
`src/api/main.py` — aquele **sempre** consulta o bot externo ao vivo, sem
checar `code_cache` primeiro. O endpoint de CHI deve checar cache antes.

---

## 6. Pontos em aberto (decidir antes de implementar)

1. **Chave de consulta**: a técnica vai informar o código do **componente**
   (`FU001`) ou o código da **instalação** (`INST12345`) e a API devolve todos
   os componentes daquela instalação? (A tabela de chaves a montante hoje é
   por instalação, não por componente isolado.)
2. **Persistência do componente no cache**: decidir se `meters`/`chaves_montante`
   passa a ser vinculada também a `code_cache` (hoje só existe via
   `network_queries`), para que cache-hits também tragam a tabela de componentes.
3. **Timeout síncrono**: quanto tempo a API pode segurar a requisição esperando
   resposta do bot externo (hoje `BOT_TERCEIRO_TIMEOUT=30s`)? Isso define se o
   endpoint deve ser síncrono ou "polling" (consulta assíncrona + endpoint de
   status).
4. **Autenticação**: reaproveitar `X-API-Key` (já existe em `settings.api_key`)
   ou criar uma chave dedicada para esse consumidor externo.
5. **Parse on-read vs backfill** (novo, seção 0): a API vai parsear o
   `raw_response` na hora (mais simples, mais lento por request) ou vamos
   primeiro rodar um backfill que popula `parsed_data`/`meters` pros 994
   registros existentes e ajustar o worker pra persistir daqui pra frente
   (mais trabalho agora, resposta mais rápida depois)?

---

## 7. Tabela para apresentar ao Naeg — o que temos disponível

Objetivo: mostrar pra ele o que já existe no banco, pra decidir junto qual
nível de "clientes" o cálculo de CHI realmente precisa (ver ponto 6.1 acima).

### 7.1 — Ao consultar um código de EQUIPAMENTO/INSTALAÇÃO, retornamos:

| Campo | Exemplo | Descrição |
|---|---|---|
| `codigo` | `INST12345` | código consultado |
| `tipo` | `Transformador` | Transformador / Religador / Chave Fusível / Disjuntor / Seccionalizador |
| `poste_referencia` | `98765` | poste onde o equipamento está instalado |
| `alimentador` | `BJU01J3` | alimentador da rede |
| `perimetro` | `RURAL` | perímetro/área |
| `potencia` | `75 kVA` | potência (se transformador) |
| `tensao_primaria` / `tensao_secundaria` | `13.8 kV` / `220/127 V` | tensões |
| `fase` | `ABC` | fases |
| `situacao` | `LIGADO` | situação operacional |
| **`clientes`** | `160` | **total de clientes atendidos por esse equipamento (número único)** |
| `latitude` / `longitude` | `-5.5265, -47.4818` | coordenadas |

### 7.2 — A mesma consulta também traz uma tabela interna de "chaves a montante"
(hierarquia de proteção acima do equipamento), uma linha por componente:

| Campo | Exemplo | Descrição |
|---|---|---|
| `tipo` (componente) | `FU`, `CF`, `RG`, `DJ`, `SE` | tipo da chave/proteção |
| `code` | `FU001` | código daquele componente específico |
| `elo` | `6K`, `10K`, `LAM` | elo/fusível |
| **`clientes`** | `42` | **clientes atendidos a partir daquele componente (um número por linha)** |
| `trafos` | `3` | transformadores a jusante daquele componente |
| `observacao` | — | texto livre, se houver |

### 7.3 — A pergunta pro Naeg, em uma frase

> "O código que vocês vão informar na consulta é o do **equipamento/instalação**
> (aí usamos o campo único `clientes` da tabela 7.1) ou é o código de uma
> **chave específica** dentro da hierarquia, tipo `FU001`/`CF002` (aí usamos a
> linha correspondente da tabela 7.2)? E, se for o segundo caso, o sistema de
> vocês já sabe de antemão qual chave quer consultar, ou espera que a API
> devolva a lista inteira de chaves daquela instalação de uma vez?"

Isso decide o formato de request/response do endpoint (seção 4) e fecha o
ponto em aberto 6.1.


