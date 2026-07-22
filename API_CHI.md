# API_CHI — Consulta de Componentes para Cálculo de CHI

> Documento de especificação e status de implementação da API de consulta
> usada pela equipe técnica (via "Naeg") para calcular o **CHI**
> (tempo de programação × número de clientes do componente).
>
> **Status: implementado.** Endpoint `GET /api/v1/chi/{codigo}` funcional
> em modo cache (fallback ao vivo ativa automaticamente assim que a conta
> Telegram dedicada — `CONSULTA_API_TELEGRAM_*` no `.env` — for configurada).

---

## 1. Achado que motivou a reconstrução (histórico)

Verificado direto no Postgres de produção em 2026-07-22: o parser antigo
(`src/exporters/parser.py` / `parser_equipamento.py`) nunca persistia nada
de volta no banco — `parsed_data` estava `NULL` em 100% de 994 linhas e a
tabela `meters` (que deveria guardar clientes por componente) tinha 0
registros. Só o texto bruto (`raw_response`) era salvo.

Isso motivou a reconstrução do projeto em `/home/ti/project/bot_integrador`
com: (1) tabelas estruturadas novas (`postes`, `equipamentos`,
`componentes`), (2) um parser reescrito do zero
(`src/parsing/poste.py`, `src/parsing/equipamento.py`), (3) um serviço de
persistência compartilhado, e (4) um segundo cliente Telegram exclusivo
para consultas via API.

---

## 2. Arquitetura implementada

```
                    ┌─────────────────────┐
Bot Telegram DPL →  │  src/userbot/        │
(fluxo em tempo     │  client.py           │──┐
 real, fila async)  └─────────────────────┘  │
                                               │
                    ┌─────────────────────┐   ▼   ┌──────────────────────────┐
API (Naeg/CHI)  →   │  src/userbot_        │──────▶│ persistencia_estruturada │
(request/response   │  consulta_api/       │       │ (src/services/)          │
 síncrono, sem       │  client.py           │       │                          │
 fila)               └─────────────────────┘       │  parse (src/parsing/)    │
                                                     │  → upsert postes/        │
                                                     │    equipamentos/         │
                                                     │    componentes           │
                                                     └──────────────────────────┘
```

Os dois clients Telegram são contas **separadas** (`telegram_*` vs
`consulta_api_telegram_*` no `.env`), cada uma com sua própria linha em
`telethon_sessions` (`SESSION_ID = "userbot"` vs `"userbot_consulta_api"`)
e seu próprio `asyncio.Lock` — não competem entre si, mas ambas chamam o
mesmo `persistencia_estruturada.salvar(...)`, então qualquer consulta feita
por qualquer um dos dois vira dado estruturado consultável pelos dois lados.

---

## 3. Schema — tabelas `postes`, `equipamentos`, `componentes`

Ver `src/database/models_estruturados.py`. Resumo dos campos relevantes
pro CHI:

> ✅ **Confirmado com o Naeg em 2026-07-22** (validado contra o texto bruto
> real de um equipamento, código `0053317`): o campo que o CHI usa é
> **`equipamentos.clientes_total`** — o "Clientes: 142" do **cabeçalho** da
> resposta, 1 número agregado por equipamento. Não é a quebra por
> componente da seção "CHAVES A MONTANTE". A tabela `componentes` continua
> sendo persistida (dado útil, já vem de graça na mesma consulta), mas
> **não é mais o campo crítico pro cálculo do CHI** — `clientes_total` é.

**`equipamentos`** (1 linha por `code`): `tipo`, `alimentador`,
`poste_referencia`, **`clientes_total`** (⭐ campo do CHI, agregado do
cabeçalho), `situacao`, `latitude`/`longitude`, entre outros.

**`componentes`** (filha de `equipamentos`, 1 linha por chave a montante —
dado suplementar, não crítico pro CHI):

| Campo | Exemplo | Descrição |
|---|---|---|
| `tipo` | `FU`, `CF`, `RG`, `DJ`, `SE` | tipo da chave/proteção |
| `componente_code` | `FU001` | código daquele componente específico |
| `elo` | `6K`, `10K`, `LAM` | elo/fusível |
| `clientes` | `42` | clientes a partir daquele componente (não é o do CHI) |
| `trafos` | `3` | transformadores a jusante daquele componente |
| `ordem` | `0, 1, 2...` | ordem original na tabela de resposta do bot |

Atualização: a cada nova consulta de um equipamento, seus `componentes` são
**substituídos por completo** (delete + insert) — nunca duplica entre
atualizações.

**`postes`** (1 linha por `code`): `latitude`/`longitude`, `alimentadores`,
`cabos_mt`/`cabos_bt`, `estruturas_mt`/`estruturas_bt` (todos JSON, listas).

Estado atual do banco (após backfill de todo o histórico existente):
**252 postes, 378 equipamentos, 3604 componentes** — nenhum com `clientes`
nulo.

---

## 4. Endpoint

```
GET /api/v1/chi/{codigo}?tipo=poste|equipamento
Header: X-API-Key: <settings.api_key>
```

Fluxo (`src/api/routes/chi.py`):

1. Busca em `postes` ou `equipamentos` (+ `componentes` via join) pelo `code`.
2. Se achar → responde direto, `origem: "cache"`.
3. Se não achar:
   - Se `userbot_consulta_api` **não estiver configurado** (sem credenciais
     ainda) → **404 direto** ("consulta ao vivo indisponível").
   - Se estiver configurado → consulta ao vivo, salva via
     `persistencia_estruturada`, responde `origem: "bot_externo"`.
4. Se o bot terceiro responder "não cadastrado" → 404.
5. Timeout na consulta ao vivo → 504.

### Exemplo de resposta — equipamento (200, cache)

```json
{
  "success": true,
  "codigo": "0753459",
  "tipo": "equipamento",
  "origem": "cache",
  "equipamento": {
    "code": "0753459",
    "tipo": "Chave Fusível",
    "alimentador": "SRT-01C4",
    "poste_referencia": "550121",
    "clientes_total": 169,
    "situacao": "OPERACAO",
    "componentes": [
      {"tipo": "FU", "componente_code": "0753459", "elo": "6K", "clientes": 169, "trafos": 30},
      {"tipo": "RG", "componente_code": "3015807", "elo": null, "clientes": 466, "trafos": 102}
    ]
  }
}
```

### Exemplo de resposta — poste (200, cache)

```json
{
  "success": true,
  "codigo": "1022314",
  "tipo": "poste",
  "origem": "cache",
  "poste": {
    "code": "1022314",
    "latitude": -5.816122251,
    "longitude": -47.137888381,
    "alimentadores": ["GEL01C1"],
    "cabos_mt": ["ALUMINIO NU 1/0 AWG CA"],
    "cabos_bt": []
  }
}
```

### Erros

| Status | Motivo |
|---|---|
| 401 | API key inválida/ausente |
| 404 | código não encontrado (cache e/ou bot externo) |
| 422 | `tipo` inválido (só aceita `poste`/`equipamento`) |
| 504 | timeout na consulta ao vivo |

Testado de ponta a ponta (`curl` local): cache-hit poste, cache-hit
equipamento, 404 código inexistente, 401 API key errada — todos OK.

---

## 5. Ativação do fallback ao vivo

Assim que a conta Telegram dedicada for criada, preencher no `.env`:

```
CONSULTA_API_TELEGRAM_API_ID=
CONSULTA_API_TELEGRAM_API_HASH=
CONSULTA_API_TELEGRAM_PHONE=
```

Nenhuma mudança de código é necessária — `userbot_consulta_api.is_configured`
passa a `True` automaticamente e o endpoint passa a consultar ao vivo em
cache-miss. No primeiro login, o Telethon vai pedir código de verificação
(mesmo fluxo do userbot original) — a sessão fica salva em
`telethon_sessions` (linha `"userbot_consulta_api"`), não precisa logar de
novo depois.

---

## 6. Pontos em aberto

1. **Autenticação dedicada**: hoje reaproveita `X-API-Key` (`settings.api_key`,
   mesma chave do endpoint `/api/v1/consulta`). Avaliar se o Naeg precisa de
   uma chave própria, dedicada a esse consumidor.
2. **Cache TTL**: o endpoint hoje responde do cache estruturado sem checar
   idade/TTL (diferente do `code_cache`, que tem 7 dias). Se o CHI precisar
   de dado sempre atualizado, avaliar `forcar_atualizacao=true` como query
   param (ainda não implementado).
