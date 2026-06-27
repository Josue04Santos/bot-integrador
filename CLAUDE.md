# CLAUDE.md

Este arquivo fornece orientações ao Claude Code (claude.ai/code) ao trabalhar com o código deste repositório.

## Visão Geral do Projeto

**Bot Integrador DPL Construções** — Bot de automação para Telegram que processa consultas em lote ao `@ReincidenciasBot` (bot de dados de rede elétrica), persiste os resultados em banco de dados e exporta arquivos geográficos (KML + GPX + CSV) para operadores de campo. Projeto proprietário de uso interno da DPL Construções.

## Comandos

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar o bot (sempre como módulo, nunca como script)
python -m src.main

# Migrations do banco de dados
alembic upgrade head
alembic revision --autogenerate -m "descrição"
alembic downgrade -1
alembic history

# Rodar testes
pytest
pytest tests/test_route_optimizer.py              # arquivo de teste específico
pytest tests/test_route_optimizer.py::test_name  # teste individual

# Smoke tests (verifica imports e ligações)
python -c "from src.bot.application import create_dispatcher; print('OK')"
python -c "from src.userbot.worker import worker_loop; print('OK')"
python -c "from src.exporters import generate_bundle; print('OK')"
```

## Arquitetura

A aplicação executa três tarefas concorrentes dentro de um único `asyncio.gather()` em `src/main.py`:

1. **Bot aiogram** (`src/bot/`) — Interface Telegram para operadores. Trata `/start`, `/kml`, `/whoami`, `/status` e comandos admin. Usa FSM (`QueryStates`) para coletar códigos em lote dos usuários.

2. **Worker loop** (`src/userbot/worker.py`) — Consome a `QueryQueue` (singleton `asyncio.Queue` em memória em `src/dispatcher/queue.py`). Para cada `QueueItem`, chama o userbot, atualiza o banco e envia o resultado de volta ao usuário.

3. **Userbot Telethon** (`src/userbot/client.py`) — Faz login como uma conta real do Telegram para interagir com o `@ReincidenciasBot`. Usa fluxo conversacional: envia `/PTE` ou `/EQP`, aguarda o prompt, envia o código e coleta a resposta. **A sessão é persistida na tabela `telethon_sessions` no Postgres** (não em arquivo `.session`).

### Ciclo de Vida de uma Consulta

```
Usuário envia códigos → handler query.py →
  Cria QueryBatch + registros NetworkQuery (status: pending) →
  Enfileira QueueItem → worker consome →
  UserbotClient.query_poste() / query_equipamento() →
  Atualiza banco (status: received/timeout/error) →
  Notifica usuário (resultado individual) →
  Se lote concluído: envia resumo + botão de download
```

### Pipeline de Exportação (`src/exporters/__init__.py:generate_bundle`)

Quando o usuário clica em "Baixar" ou executa `/kml <batch_id>`:
1. Carrega todos os registros `NetworkQuery` do lote
2. Faz parse das respostas brutas → `PosteData` ou `EquipamentoData` (ramificado por `query_type`)
3. Executa **OR-Tools TSP** (`RouteOptimizer`) nos postes com coordenadas para ordenação ótima
4. Chama **OSRM** (`src/services/osrm_client.py`) para geometria rodoviária real
5. Gera KML + GPX (postes) + GPX (equipamentos) + 2 CSVs + TXT de inválidos
6. Retorna `ExportBundle` com os bytes de todos os arquivos

O módulo `adapter.py` desacopla `PosteData` (domínio exporters) de `RoutePoint` (domínio services).

## Convenções Importantes

### Execução como módulo
Sempre execute com `python -m src.main`, nunca com `python src/main.py`. O `conftest.py` adiciona a raiz do projeto ao `sys.path` para o pytest, mas a forma de módulo é obrigatória em produção.

### Configurações
Instância única de settings via `from src.config import settings`. Todas as chaves são **snake_case** (`settings.telegram_bot_token`, não `settings.TELEGRAM_BOT_TOKEN`). Carregadas do `.env` pelo `pydantic-settings`. Para alternar SQLite ↔ PostgreSQL: defina `database_backend=postgres` no `.env`.

### Banco de Dados
- Singleton `db = DatabaseManager()` em `src/database/connection.py`
- Sempre use `async with db.session() as session:` — faz commit automático no sucesso e rollback em exceção
- Chaves primárias são UUIDs gerados por `uuid7()` de `src/database/types.py`
- Models com SQLAlchemy 2.0 usando colunas tipadas com `Mapped`
- Schema: `AuthorizedUser` → `QueryBatch` (1:N) → `NetworkQuery` (1:N) → `Meter`

### Handlers do Bot
Handlers são instâncias de `Router` do aiogram, registrados em ordem em `src/bot/handlers/__init__.py:register_handlers()`. A ordem importa — `admin_router` é o primeiro, `help_router` é o último (catch-all). A autenticação é aplicada pelo `AuthMiddleware` (bloqueia usuários ausentes da tabela `authorized_users` ou com `active=False`). O middleware injeta `auth_user_id`, `auth_user_role` e `auth_user_full_name` no `data` dos handlers.

### Design dos Parsers
Tanto `src/exporters/parser.py` (postes) quanto `src/exporters/parser_equipamento.py` (equipamentos) fazem parse das respostas brutas do `@ReincidenciasBot`. Sempre retornam um objeto de dados (nunca lançam exceção) — verifique `.parse_error` para detectar falhas. Os padrões regex são compilados em nível de módulo por questão de performance. A resposta bruta é sempre salva em `NetworkQuery.raw_response` para permitir reprocessamento se o parser mudar.

### Logs
Usa `structlog` em todo o projeto. Obtenha um logger com `from src.utils.logger import get_logger; logger = get_logger(__name__)`. Em desenvolvimento: saída colorida no console. Em produção: JSON.

### Tipos de Consulta
Valores de `query_type` no banco: `"poste"` e `"instalacao"` (não `"equipamento"`). O userbot envia `/PTE` para postes e `/EQP` para equipamentos. Essa inconsistência de nomenclatura (`instalacao` no banco vs `equipamento` na UI) é intencional — reflete a terminologia do bot upstream.

## Configuração do Ambiente

Copie `.env.example` para `.env`. Variáveis obrigatórias:
- `TELEGRAM_BOT_TOKEN` — obtido com @BotFather
- `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_PHONE` — de [my.telegram.org](https://my.telegram.org)

O banco padrão é SQLite em `data/bot_integrador.db`. Para usar Postgres, defina `database_backend=postgres` e as variáveis `POSTGRES_*` no `.env`.

A sessão do Telethon requer um **primeiro login interativo** (código de verificação + 2FA opcional). Após isso, a string de sessão é salva na tabela `telethon_sessions` e reutilizada automaticamente.

## Autorização do Primeiro Usuário

Usuários precisam ser inseridos manualmente em `authorized_users` antes de usar o bot (o comando `/grant` ainda não existe — está no roadmap):

```python
from src.database.connection import db
from src.database.models import AuthorizedUser

async with db.session() as s:
    s.add(AuthorizedUser(tg_id=123456789, full_name="Nome", role="admin"))
    await s.commit()
```

## Infraestrutura

- **Deploy**: Docker Compose em `deploy/docker/` (Dockerfile + compose)
- **Nginx**: configuração em `deploy/nginx/`
- **OSRM**: usa o servidor público `router.project-osrm.org` (gratuito, uso justo). Limitado a ~1 req/s. Para uso intenso em produção, hospede o próprio servidor OSRM.
- **Arquivos de exportação**: gerados em memória como bytes (não são gravados em disco no pipeline de exportação)
