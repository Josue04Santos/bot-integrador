# Teste em Massa — 14 Postes (Padrão Alternado Cache/Bot)

> Data: 2026-07-01  
> Lote: `#019f1ef7`  
> Tipo: POSTE  
> Padrão: `1C · 1S · 1C · 2S · 2C · 3S · 2C · 2S`

---

## Resultado por Código

| # | Código | Esperado | Status | Tempo | Observação |
|---|--------|----------|--------|-------|------------|
| 1 | `1005792` | 📦 cache | ✅ received | 0ms | Cache funcionou |
| 2 | `1005800` | 🌐 bot externo | ✅ received | 7.490ms | OK |
| 3 | `1038312` | 📦 cache | ✅ received | 0ms | Cache funcionou |
| 4 | `1038314` | 🌐 bot externo | ❌ error | - | **Não cadastrado** |
| 5 | `1038316` | 🌐 bot externo | ✅ received | 9.737ms | OK (lento) |
| 6 | `1038359` | 📦 cache | ✅ received | 0ms | Cache funcionou |
| 7 | `1038361` | 📦 cache | ✅ received | 0ms | Cache funcionou |
| 8 | `1038369` | 🌐 bot externo | ⏱ timeout | - | **Sem resposta** |
| 9 | `1038370` | 🌐 bot externo | ✅ received | 7.999ms | OK |
| 10 | `1038384` | 🌐 bot externo | ✅ received | 7.559ms | OK |
| 11 | `1038387` | 📦 cache | ✅ received | 0ms | Cache funcionou |
| 12 | `1038388` | 📦 cache | ✅ received | 0ms | Cache funcionou |
| 13 | `1038398` | 🌐 bot externo | ⏱ timeout | - | **Sem resposta** |
| 14 | `1038399` | 🌐 bot externo | ✅ received | 22.560ms | OK (muito lento) |

---

## Resumo

| Métrica | Valor |
|---------|-------|
| Total | 14 |
| ✅ Sucesso | 11 |
| ❌ Não cadastrado | 1 (`1038314`) |
| ⏱ Timeout | 2 (`1038369`, `1038398`) |
| Duração total do lote | 150s |

---

## Análise — Cache

**6 cache hits, todos corretos e instantâneos (0ms).**  
O sistema entregou do banco sem nenhuma chamada ao bot externo.

Tempo economizado estimado: 6 × ~7s = **~42 segundos**.

---

## Análise — Bot Externo

### Tempos de resposta
| Código | Tempo |
|--------|-------|
| `1005800` | 7.490ms |
| `1038316` | 9.737ms ⚠️ acima da média |
| `1038370` | 7.999ms |
| `1038384` | 7.559ms |
| `1038399` | **22.560ms** 🔴 muito lento |
| Média normal | ~7.5s |

### Problemas encontrados

**`1038314` — Não cadastrado**  
Poste não existe no sistema externo. Tratado corretamente como erro, não salvo no cache.

**`1038369` e `1038398` — Timeout**  
Dois timeouts consecutivos (posições 8 e 13). Padrão suspeito:
- `1038369` é logo após uma sequência de 2 cache hits rápidos (posições 6 e 7)
- `1038398` é logo após outra sequência de 2 cache hits (posições 11 e 12)

**Hipótese:** cache hits consecutivos liberam itens da fila muito rápido, e o bot externo ainda está processando a consulta anterior quando a próxima chega — causando timeout.

**`1038399` — 22.5s (3x acima da média)**  
Veio logo após dois timeouts. O bot externo possivelmente estava sobrecarregado ou em estado de recuperação.

---

## Padrão Identificado — Problema Principal

```
posição 6: 1038359  → cache (0ms)
posição 7: 1038361  → cache (0ms)
posição 8: 1038369  → TIMEOUT ← bot externo não respondeu

posição 11: 1038387 → cache (0ms)
posição 12: 1038388 → cache (0ms)
posição 13: 1038398 → TIMEOUT ← bot externo não respondeu
```

**Cache hits consecutivos → próxima consulta real sofre timeout.**

Causa provável: o bot externo usa um fluxo conversacional com estado.
Quando o worker processa cache hits muito rápido, a próxima consulta real
inicia antes que a sessão conversacional anterior tenha sido limpa corretamente.

---

## Melhorias Identificadas

### 1. Delay após cache hit (prioridade alta)
Adicionar uma pausa mínima entre consultas ao bot externo,
independente de quantos cache hits ocorreram antes.

```python
# Após cache hit, aguardar antes de liberar próximo item da fila
DELAY_POS_CACHE_HIT = 1.5  # segundos
```

### 2. Retry automático em timeout (prioridade média)
Códigos com timeout poderiam ser re-enfileirados automaticamente
(1 tentativa extra) antes de serem marcados como timeout definitivo.

### 3. Detecção de timeout em sequência (prioridade baixa)
Se 2 timeouts consecutivos acontecerem, pausar a fila por alguns segundos
para deixar o bot externo se recuperar.

### 4. Timeout reduzido (prioridade baixa)
Tempo atual: 30s. Média real: ~7.5s. Poderia ser 12s com margem de segurança.
