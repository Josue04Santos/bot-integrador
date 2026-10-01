# 📚 Documentação — Bot Integrador DPL

↩ [README do projeto](../README.md)

Índice central. Os documentos continuam na raiz do repositório, onde sempre estiveram; aqui só ficam os links,
agrupados por assunto e com o estado de cada um.

## ✅ Vigentes

| Guia | Assunto |
|---|---|
| [`../README.md`](../README.md) | Visão geral, instalação, configuração, comandos, modelo de dados, troubleshooting e roadmap |
| [`../API_CHI.md`](../API_CHI.md) | Especificação e status da API de CHI (`GET /api/v1/chi/{codigo}`), tabelas estruturadas e as duas contas Telegram |
| [`../CLAUDE.md`](../CLAUDE.md) | Ficha operacional: dev × produção, publicação e rollback, segredos, pegadinhas e pendências |
| [`../.env.example`](../.env.example) | Modelo das variáveis de ambiente (sem valores) |
| [`../deploy/systemd/bot-integrador.service`](../deploy/systemd/bot-integrador.service) | Unidade systemd usada em produção |
| [`../alembic/versions/`](../alembic/versions/) | Histórico de migrations do banco |

## 🗺️ Rotas e OsmAnd

| Guia | Assunto |
|---|---|
| [`../OSMAND_ROTAS.md`](../OSMAND_ROTAS.md) | Guia de roteirização automática no OsmAnd |
| [`../OSMAND_ROTAS_COMPARACAO.md`](../OSMAND_ROTAS_COMPARACAO.md) | Antes × depois do GPX (só waypoints → rota) |
| [`../SOLUCAO_FINAL.md`](../SOLUCAO_FINAL.md) | Solução implementada para roteirização no OsmAnd (22/05/2026) |
| [`../STATUS_OSMAND.txt`](../STATUS_OSMAND.txt) | Status da correção do OsmAnd (maio/2026) |

## 🔎 Diagnósticos e testes

| Guia | Assunto |
|---|---|
| [`../ANALISE_BOT_EXTERNO.md`](../ANALISE_BOT_EXTERNO.md) | Comportamento observado do `@ReincidenciasBot` (01/07/2026) |
| [`../TESTE_MASSA_01_07.md`](../TESTE_MASSA_01_07.md) | Teste em massa com 14 postes alternando cache e bot (01/07/2026) |

## 🗂️ Histórico (relatórios antigos — conferir contra o código antes de usar)

| Guia | Assunto |
|---|---|
| [`../CODE_ANALYSIS_REPORT.md`](../CODE_ANALYSIS_REPORT.md) | Análise estática do código (22/05/2026) |
| [`../ANALYSIS_SUMMARY.txt`](../ANALYSIS_SUMMARY.txt) | Resumo da mesma análise |
| [`../ACTION_ITEMS.md`](../ACTION_ITEMS.md) | Lista de issues levantadas na análise de maio |
| [`../QUICK_FIX_GUIDE.md`](../QUICK_FIX_GUIDE.md) | Guia rápido de correções da análise de maio |
| [`../COMANDOS.md`](../COMANDOS.md) | Anotação da criação do serviço systemd |
| [`../README_OLD.md`](../README_OLD.md) | Versão anterior do README |
| [`../repomix-output.md`](../repomix-output.md) | Dump do código inteiro (424 KB) — conferir que não contém `.env` antes de compartilhar |

<!-- PREENCHER: capturas de tela (dados mascarados) em doc/imagens/ -->
