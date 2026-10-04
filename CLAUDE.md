# bot-integrador (Bot Integrador DPL) — ficha do projeto

> Ficha padrão (modelo em `~/padrao/templates/FICHA-CLAUDE.md`). Todo chat lê isto antes de mexer no projeto.
> Mudou algo que está aqui (porta, serviço, fluxo, caminho)? Atualize a ficha NO MESMO COMMIT.

## 1. O que é
Bot do Telegram (aiogram + userbot Telethon) que consulta em lote o `@ReincidenciasBot` / API CHI (dados de rede
elétrica por código), grava no Postgres e exporta KML/GPX/CSV (OsmAnd, Google Earth, Excel); tem dashboard web.
**No ar**: o serviço de produção roda sem parar desde 24/07/2026 — o código é que está parado desde 24/07.

## 2. Onde fica

| O quê | Valor |
|---|---|
| Repositório | `github.com/Josue04Santos/bot-integrador` |
| Pasta de desenvolvimento | `~/dev/bot-integrador` — branch `master` (alinhado com a produção em 30/09, `dc9f387`) |
| Pasta de produção | `~/project/bot_integrador` — branch `master` (clone separado, NÃO worktree), último commit 24/07 `c4fd366` |
| Docs | `README.md`, `API_CHI.md`, `COMANDOS.md`, vários relatórios soltos (`CODE_ANALYSIS_REPORT.md`, `OSMAND_*.md`…) |

## 3. Como roda

| Parte | Dev | Produção |
|---|---|---|
| Bot + worker + dashboard | não roda | `bot-integrador.service` (sistema), `venv/bin/python -m src.main`, dashboard porta `8080` |
| Telegram | polling (`dp.start_polling` em `src/main.py`) | polling — as variáveis de webhook existem no `.env`, mas o código NÃO implementa webhook |
| Banco (Postgres `192.168.1.202`) | `bot_integrador` | `bot_integrador` (**o MESMO**) |

## 4. Fluxo de git
Um chat por vez. Antes de mexer, `git pull` no dev (dev e prod são clones separados do mesmo `master`).
Depois: commit no dev → push → `git pull` na prod. Formato em uso: frase curta / `fix:`/`feat:`. Nunca `git add -A`.

## 5. Publicar e voltar atrás
- Publicar: na prod, `git pull` + `sudo systemctl restart bot-integrador` — sempre com OK do usuário.
- Voltar atrás: `git checkout <hash anterior>` na prod + restart.
- Migração (`alembic/`): sempre perguntar antes.

## 6. Testes
```bash
cd ~/dev/bot-integrador && venv/bin/python -m pytest tests -q
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

## 8.1 Pendências (levantamento 30/09 — o chat deve mostrar estas ao abrir uma SALA deste projeto)
- **Dev e prod usam o MESMO banco** (`bot_integrador`): separar o banco de dev antes de qualquer teste.
- Serviço no ar desde 24/07 (dashboard :8080) — confirmar se alguém ainda usa o bot; webhook `startbot.dpl.srv.br` aponta para 192.168.1.212 (outro host).
- Dev estava 24 commits atrás da prod — alinhado em 30/09 (`dc9f387`).

## 9. Histórico e memórias relacionadas
Nenhuma memória específica (projeto citado em `project_padronizacao_fichas_projetos.md`). Possível antecessor: `~/dev/fluxo-operacional` (bot/userbot/KML, mai/2026).
