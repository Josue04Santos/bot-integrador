# bot-integrador (Bot Integrador DPL) — ficha do projeto

> Ficha padrão (modelo em `~/projetos/_templates/FICHA-CLAUDE.md`). Todo chat lê isto antes de mexer no projeto.
> Mudou algo que está aqui (porta, serviço, fluxo, caminho)? Atualize a ficha NO MESMO COMMIT.

## 1. O que é
Bot do Telegram (aiogram + userbot Telethon) que consulta em lote o `@ReincidenciasBot` / API CHI (dados de rede
elétrica por código), grava no Postgres e exporta KML/GPX/CSV (OsmAnd, Google Earth, Excel); tem dashboard web.
**No ar**: o serviço de produção roda sem parar desde 24/07/2026 — o código é que está parado desde 24/07.

## 2. Onde fica

| O quê | Valor |
|---|---|
| Repositório | `github.com/Josue04Santos/bot-integrador` |
| Pasta de desenvolvimento | `~/projetos/dev/bot-integrador` — branch `master`, **24 commits atrás da produção** (último 22/07) |
| Pasta de produção | `~/project/bot_integrador` — branch `master` (clone separado, NÃO worktree), último commit 24/07 `c4fd366` |
| Docs | `README.md`, `API_CHI.md`, `COMANDOS.md`, vários relatórios soltos (`CODE_ANALYSIS_REPORT.md`, `OSMAND_*.md`…) |

## 3. Como roda

| Parte | Dev | Produção |
|---|---|---|
| Bot + worker + dashboard | não roda | `bot-integrador.service` (sistema), `venv/bin/python -m src.main`, dashboard porta `8080` |
| Webhook Telegram | — | `WEBHOOK_ENABLED=true`, URL em `startbot.dpl.srv.br` (nginx → 192.168.1.212, não este host — conferir) |
| Banco (Postgres `192.168.1.202`) | `bot_integrador` | `bot_integrador` (**o MESMO**) |

## 4. Fluxo de git
Um chat por vez. Hoje o dev está atrás: antes de mexer, `git pull` no dev (trazer os 24 commits da prod).
Depois: commit no dev → push → `git pull` na prod. Formato em uso: frase curta / `fix:`/`feat:`. Nunca `git add -A`.

## 5. Publicar e voltar atrás
- Publicar: na prod, `git pull` + `sudo systemctl restart bot-integrador` — sempre com OK do usuário.
- Voltar atrás: `git checkout <hash anterior>` na prod + restart.
- Migração: há `alembic/` só na prod — sempre perguntar antes.

## 6. Testes
```bash
cd ~/projetos/dev/bot-integrador && venv/bin/python -m pytest tests -q
```

## 7. Dados e segredos
- `.env` nas duas pastas (tokens do bot, `API_ID/API_HASH/PHONE` de duas contas Telegram, `POSTGRES_*`, `API_KEY`,
  `TELEGRAM_WEBHOOK_SECRET`) — gitignored. Dev ainda tem `.env.bak.20260521-202725` solto (gitignored por `.env.bak*`).
- `sessions/*.session` = login das contas Telegram (userbot) — tratar como senha, nunca apagar nem versionar.
- `repomix-output.md` (424 KB) é um dump do código inteiro — conferir que não contém `.env` antes de compartilhar.

## 8. Pegadinhas conhecidas
- **Dev e prod usam o mesmo banco** `bot_integrador` — rodar o bot do dev (ou migration) mexe nos dados reais.
- Rodar o bot do dev em paralelo usa as mesmas contas/sessões Telegram e derruba a sessão da prod.
- Logs mostram reconexão Telethon a cada ~1 min (normal até agora, mas é ruído no journal).
- Remoto tem branch `claude/claude-md-docs-682xm8` esquecida.

## 9. Histórico e memórias relacionadas
Nenhuma memória específica (projeto citado em `project_padronizacao_fichas_projetos.md`). Possível antecessor: `~/projetos/dev/fluxo-operacional` (bot/userbot/KML, mai/2026).
