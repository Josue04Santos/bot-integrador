# Análise do Comportamento — @ReincidenciasBot

> Diagnóstico executado em: 2026-07-01  
> Ferramenta: `scripts/debug_bot_externo.py`  
> Códigos testados: `3003841`, `0075566`, `0065951`, `0907855`, `2198002`

---

## Fluxo Conversacional Confirmado

O bot externo opera em **2 etapas fixas** para cada consulta:

```
NÓS        →   /PTE  ou  /EQP
BOT        ←   prompt  (1 mensagem)
NÓS        →   código
BOT        ←   resposta  (1 mensagem)
```

**Nunca envia mais de 1 mensagem por etapa.** O fluxo é simples e previsível.

---

## Prompts Exatos

| Comando | Prompt recebido |
|---------|----------------|
| `/PTE`  | `Informe o número do poste:` |
| `/EQP`  | `Informe o número do componente:` |

---

## Tempos Medidos

| Etapa | Tempo médio | Mín | Máx |
|-------|-------------|-----|-----|
| Aguardar prompt (após comando) | ~3.3s | 2.77s | 3.53s |
| Aguardar resposta (após código) | ~3.0s | 2.91s | 3.05s |
| **Total por consulta** | **~6.3s** | 5.7s | 6.5s |

---

## Resultados por Código

| Código | Tipo testado | Status | Observação |
|--------|-------------|--------|------------|
| `3003841` | POSTE (`/PTE`) | ❌ Não cadastrado | `"Poste não cadastrado."` |
| `3003841` | EQUIPAMENTO (`/EQP`) | ✅ Sucesso | É uma **Chave Fusível** no alimentador SLR-01C2 |
| `0075566` | EQUIPAMENTO (`/EQP`) | ✅ Sucesso | Transformador IPC-01C5, 150kVA, 216 clientes |
| `0065951` | EQUIPAMENTO (`/EQP`) | ✅ Sucesso | Secionadora IPC-01C2, 294 clientes |
| `0907855` | EQUIPAMENTO (`/EQP`) | ✅ Sucesso | Transformador AMT-01C1, 150kVA, 134 clientes |
| `2198002` | EQUIPAMENTO (`/EQP`) | ✅ Sucesso | Chave Fusível AGV-01C1, 8 clientes |

> **Nota:** `3003841` é um equipamento disfarçado de poste — o número existe no sistema, mas como componente, não como poste.

---

## Estrutura da Resposta

### Resposta de sucesso (`/EQP`)
```
Instalação: **{codigo}**

**Alimentador: **{alimentador}
**Perímetro: **URBANO | RURAL
**Tipo: **{tipo ou vazio}
**Poste: **{poste_referencia}
**Potência: **{potencia} ou "Não Informada"
**Tensão Primária: **{tensao} Volts
**Tensão Secundária: **{tensao} Volts  (ausente em chaves/fusíveis)
**Fase: **{fase}
**Clientes: **{n}
**Situação: **OPERACAO | DESLIGADO | ...

**Localização**
https//www.google.com.br/maps/place/{lat},{lng}

CHAVES A MONTANTE ATÉ A SUBESTAÇÃO
Componente        Elo   Cliente   Trafos
-------------------------------------------------
{tipo}  {codigo}  {elo}  {clientes}  {trafos}
...
```

### Resposta de erro
```
Poste não cadastrado.
```
ou
```
Comando não reconhecido! **{codigo}** Favor refazer o processo novamente.
```

---

## Conclusões e Melhorias Identificadas

### ✅ O que já funciona bem
- Fluxo de 2 etapas é estável e previsível
- Sempre **1 mensagem por etapa** — sem fragmentação
- Tempo por consulta: ~6s (consistente)

### ⚠️ Problemas identificados e corrigidos
| Problema | Causa | Correção aplicada |
|----------|-------|-------------------|
| "Comando não reconhecido" após cache hit | Fila com mensagem residual do prompt anterior | `sleep(0.8)` antes de limpar a fila |
| "Não cadastrado" contado como sucesso | Resposta não era `None`, era texto | Detecção de padrões inválidos |
| Dados "não cadastrado" no cache | Não havia filtro na hora de salvar | Não salva se resposta for inválida |

### 💡 Melhorias possíveis no futuro
- **Detecção automática de tipo:** se `/PTE` retornar "não cadastrado", tentar `/EQP` automaticamente (ex: `3003841`)
- **Timeout adaptativo:** prompt chega em ~3.3s, resposta em ~3.0s — podemos reduzir o timeout atual de 30s para 8s
- **Validação do prompt:** checar se o texto recebido é realmente o prompt esperado antes de enviar o código

---

## Parâmetros Recomendados

```ini
# .env
BOT_TERCEIRO_TIMEOUT=10   # atual: 30s — desnecessário, 10s é suficiente
```
