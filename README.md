# 🤖 Bot Integrador DPL Construções

> **Bot de automação para consulta de dados de rede elétrica via Telegram**
> Integra-se ao `@ReincidenciasBot` da DPL Construções, processa lotes de consultas em paralelo, persiste em banco e exporta resultados como **KML (Google Earth)** + **CSV**.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.28-2CA5E0?logo=telegram&logoColor=white)](https://aiogram.dev/)
[![Telethon](https://img.shields.io/badge/Telethon-1.43-1E96C8?logo=telegram&logoColor=white)](https://docs.telethon.dev/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](#-licença)

---

## 📑 Sumário

- [🎯 Visão Geral](#-visão-geral)
- [✨ Funcionalidades](#-funcionalidades)
- [🏗️ Arquitetura](#️-arquitetura)
- [📂 Estrutura do Projeto](#-estrutura-do-projeto)
- [🚀 Quickstart](#-quickstart)
- [⚙️ Configuração](#️-configuração)
- [🎮 Uso do Bot](#-uso-do-bot)
- [🗄️ Modelo de Dados](#️-modelo-de-dados)
- [🧪 Desenvolvimento](#-desenvolvimento)
- [📊 Roadmap](#-roadmap)
- [🛠️ Stack Técnica](#️-stack-técnica)
- [🧭 Troubleshooting](#-troubleshooting)
- [📜 Licença](#-licença)

---

## 🎯 Visão Geral

O **Bot Integrador DPL Construções** é uma ponte automatizada entre operadores de campo e o sistema de consulta de rede elétrica da DPL Construções. Ele resolve três problemas operacionais:

| Problema | Solução |
|----------|---------|
| 🐌 Consultas manuais uma a uma no `@ReincidenciasBot` | ⚡ Lotes de até **500 códigos** processados em paralelo |
| 📋 Resultados perdidos em texto puro no chat | 🗄️ **Persistência estruturada** em banco com histórico |
| 🗺️ Coordenadas isoladas sem visualização geográfica | 📍 Exportação **KML + CSV** para Google Earth/Excel |

### Quem usa?

Operadores de campo, despachantes e analistas da distribuidora de energia que precisam:
- Consultar dados de **postes** (alimentador, estruturas, cabos, coordenadas)
- Consultar dados de **equipamentos/instalações** (medidores, chave montante)
- Plotar pontos geográficos em mapas para inspeção e planejamento

---

## ✨ Funcionalidades

### 🔍 Consultas em Lote

- ✅ Aceita **1 código, vários códigos** (separados por vírgula/espaço) ou **arquivo `.txt`**
- ✅ Limite de **500 códigos por lote**
- ✅ Processamento **assíncrono e paralelo** via fila interna
- ✅ Estado persistente — sobrevive a reinicializações do bot
- ✅ Resultados individuais entregues em tempo real no chat

### 🤖 Userbot Inteligente

- ✅ Cliente Telethon que se loga como usuário real para consultar `@ReincidenciasBot`
- ✅ Detecção automática de **timeout**, **erro** e **resposta vazia**
- ✅ Parser robusto que extrai coordenadas, alimentador, estruturas e cabos

### 📍 Exportação Geográfica

- ✅ **KML (Google Earth)** com placemarks agrupados por alimentador
- ✅ **CSV** (delimitador `;`, compatível com Excel-BR)
- ✅ Botão "📍 Baixar KML + CSV" aparece automaticamente ao concluir o lote
- ✅ Comando manual `/kml <id_lote>` para baixar lotes antigos
- ✅ Caption rica: total de pontos, com/sem coordenadas

### 🔔 Notificações Automáticas

- ✅ Mensagem de **conclusão do lote** com estatísticas completas
- ✅ Métricas: total, sucessos, erros, timeouts, duração

### 🛡️ Controle de Acesso

- ✅ Lista de usuários autorizados (`AuthorizedUser`) gerenciada em banco
- ✅ Middleware de autenticação em todos os handlers
- ✅ Comando `/whoami` para inspeção do próprio perfil

### 🌐 API REST (Bonus)

- ✅ Endpoints FastAPI para integração externa
- ✅ Documentação automática em `/docs` (Swagger)

---

## 🏗️ Arquitetura

### Visão de Alto Nível
┌─────────────────────────────────────────────────────────────┐ │ USUÁRIO TELEGRAM │ └──────────────────────┬──────────────────────────────────────┘ │ ▼ ┌──────────────────────┐ │ BOT (aiogram 3.28) │ ← interface conversacional │ /start /help /kml │ └──────────┬───────────┘ │ enfileira ▼ ┌──────────────────────┐ │ FILA (in-memory) │ ← QueryBatch + NetworkQuery └──────────┬───────────┘ │ consome ▼ ┌──────────────────────┐ │ WORKER (asyncio) │ ← processa em paralelo └──────────┬───────────┘ │ consulta via ▼ ┌──────────────────────┐ │ USERBOT (Telethon) │ ← conversa com @ReincidenciasBot └──────────┬───────────┘ │ persiste ▼ ┌──────────────────────┐ ┌─────────────────┐ │ BANCO (SQLite/PG) │────────▶│ EXPORTERS │ │ via SQLAlchemy 2.0 │ │ KML + CSV │ └──────────────────────┘ └─────────────────┘




### Camadas

| Camada | Responsabilidade | Tecnologia |
|--------|------------------|------------|
| **Bot** | Interface conversacional, handlers de comandos | aiogram 3 |
| **Userbot** | Cliente que conversa com bot terceiro | Telethon |
| **Dispatcher** | Fila assíncrona de consultas | asyncio |
| **Exporters** | Geração de KML + CSV | simplekml |
| **Services** | Parser de respostas do `@ReincidenciasBot` | regex puro |
| **Database** | Persistência ORM async | SQLAlchemy 2.0 |
| **API** | Endpoints REST (opcional) | FastAPI |

---

## 📂 Estrutura do Projeto
bot-integrador/ ├── src/ │ ├── main.py # entry point — sobe bot + worker │ ├── config.py # configurações globais │ │ │ ├── bot/ # 🤖 BOT TELEGRAM (aiogram) │ │ ├── application.py # factory do dispatcher │ │ ├── handlers/ # comandos & callbacks │ │ │ ├── start.py # /start, /status, menu inicial │ │ │ ├── help.py # /help │ │ │ ├── query.py # fluxo POSTE / EQUIPAMENTO │ │ │ ├── export.py # /kml + botão de download │ │ │ └── whoami.py # /whoami │ │ ├── keyboards/ # teclados inline │ │ ├── middlewares/ # auth, logging, rate limit │ │ └── states/ # FSM (Finite State Machine) │ │ │ ├── userbot/ # 🛰️ CLIENTE TELETHON │ │ ├── client.py # singleton do TelegramClient │ │ ├── session_manager.py # consultas síncronas ao bot terceiro │ │ └── worker.py # loop que consome a fila │ │ │ ├── dispatcher/ # 📥 FILA DE CONSULTAS │ │ └── queue.py │ │ │ ├── exporters/ # 📦 GERAÇÃO DE ARQUIVOS │ │ ├── kml_builder.py # KML agrupado por alimentador │ │ ├── csv_builder.py # CSV com delimitador ';' │ │ ├── parser.py # extrai dados estruturados das queries │ │ └── styles.py # estilos visuais do KML │ │ │ ├── services/ # 🧠 LÓGICA DE DOMÍNIO │ │ └── parser.py # parser legado (usado por session_manager) │ │ │ ├── database/ # 🗄️ PERSISTÊNCIA │ │ ├── connection.py # engine async + session factory │ │ ├── models.py # entidades SQLAlchemy │ │ └── types.py # tipos customizados (UUID, JSON) │ │ │ ├── models/ # 📋 SCHEMAS PYDANTIC │ │ └── schemas.py # PosteData, InstalacaoData, Coordenadas │ │ │ ├── api/ # 🌐 API REST (FastAPI) │ │ ├── main.py │ │ └── routes/ │ │ │ └── utils/ # 🔧 UTILITÁRIOS │ ├── config.py # Settings (pydantic-settings) │ └── logger.py # logger estruturado (structlog) │ ├── data/ # 🗃️ banco SQLite + sessões Telethon ├── exports/ # 📂 arquivos KML/CSV gerados ├── logs/ # 📝 logs estruturados ├── alembic/ # 🔄 migrations do banco │ ├── .env.example # template de variáveis ├── requirements.txt # dependências Python ├── alembic.ini # configuração de migrations └── README.md




---

## 🚀 Quickstart

### Pré-requisitos

- **Python 3.11+**
- **Telegram API credentials** ([my.telegram.org](https://my.telegram.org))
- **Bot Token** ([@BotFather](https://t.me/BotFather))
- Acesso ao `@ReincidenciasBot` (ou similar)

### Instalação

```bash
# 1. Clone o repositório
git clone <url-do-repo>
cd bot-integrador

# 2. Crie e ative o virtualenv
python3 -m venv venv
source venv/bin/activate    # Linux/Mac
# venv\Scripts\activate     # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure variáveis de ambiente
cp .env.example .env
nano .env                    # edite com suas credenciais

# 5. Rode as migrations do banco
alembic upgrade head

# 6. Suba o bot
python -m src.main
Primeiro login do userbot
Na primeira execução, o Telethon vai pedir:

Código de verificação enviado ao seu Telegram
Senha 2FA (se ativada)
A sessão é salva em data/userbot.session — não precisa logar de novo.

⚙️ Configuração
Arquivo .env
ini


# ────────────────────────────────────────────────────────
# 🤖 TELEGRAM BOT (aiogram)
# ────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...   # obtido com @BotFather
WEBHOOK_ENABLED=false                   # true em produção
TELEGRAM_WEBHOOK_URL=                   # ex: https://meudominio.com/webhook
TELEGRAM_WEBHOOK_SECRET=                # token secreto opcional

# ────────────────────────────────────────────────────────
# 🛰️ USERBOT (Telethon)
# ────────────────────────────────────────────────────────
TELEGRAM_API_ID=1234567                 # de my.telegram.org
TELEGRAM_API_HASH=abc123...             # de my.telegram.org
TELEGRAM_PHONE=+5599999999999           # com DDI
BOT_TERCEIRO_USERNAME=ReincidenciasBot  # bot consultado
BOT_TERCEIRO_TIMEOUT=30                 # segundos
TELEGRAM_SOURCE_CHAT_ID=0               # opcional

# ────────────────────────────────────────────────────────
# 🗄️ BANCO DE DADOS
# ────────────────────────────────────────────────────────
# SQLite (default — desenvolvimento)
# nenhuma config necessária — usa data/bot.db

# PostgreSQL (produção)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=bot_integrador
POSTGRES_USER=bot_user
POSTGRES_PASSWORD=senha_forte_aqui

# ────────────────────────────────────────────────────────
# ⚙️ APLICAÇÃO
# ────────────────────────────────────────────────────────
APP_ENV=development                     # development | production
APP_DEBUG=true
APP_LOG_LEVEL=INFO                      # DEBUG | INFO | WARNING | ERROR

# ────────────────────────────────────────────────────────
# 🌐 API REST (opcional)
# ────────────────────────────────────────────────────────
API_HOST=0.0.0.0
API_PORT=8000
Autorizar usuários
Antes do primeiro uso, cadastre usuários autorizados:

python


# Via shell async (exemplo)
from src.database.connection import db
from src.database.models import AuthorizedUser

async with db.session() as s:
    user = AuthorizedUser(
        telegram_id=123456789,
        nome="Josué Santos",
        role="admin",
    )
    s.add(user)
    await s.commit()
💡 Futuro: comando /grant <user_id> para admins (µ-task no roadmap).

🎮 Uso do Bot
Comandos Disponíveis



Comando	Função
/start	Menu inicial com opções POSTE e EQUIPAMENTO
/help	Ajuda completa
/status	Status do bot e da fila
/whoami	Mostra seu perfil e permissões
/kml	Ajuda do exportador
/kml <id>	Baixa KML+CSV de um lote (primeiros 8 chars do UUID)
Fluxo Típico — Consulta de Poste


1. /start
2. Clica em 🏗️ POSTE
3. Envia: 12345 67890 11111
4. Aguarda processamento (~3s por código)
5. Recebe resultados individuais
6. Recebe mensagem 🎉 Lote concluído!
7. Clica em [📍 Baixar KML + CSV]
8. Recebe arquivos prontos pro Google Earth
Formatos de Entrada


# Um código
12345

# Vários códigos (vírgula, espaço ou quebra de linha)
12345, 67890, 11111
12345 67890 11111

# Arquivo .txt (envie como anexo)
12345
67890
11111
🗄️ Modelo de Dados
Entidades Principais


┌────────────────────┐       ┌────────────────────┐
│   AuthorizedUser   │       │     QueryBatch     │
├────────────────────┤       ├────────────────────┤
│ telegram_id (PK)   │       │ id (UUID, PK)      │
│ nome               │       │ user_telegram_id   │
│ role               │       │ query_type         │
│ created_at         │       │ source             │
└────────────────────┘       │ total_count        │
                             │ success_count      │
                             │ error_count        │
                             │ timeout_count      │
                             │ status             │
                             │ created_at         │
                             │ completed_at       │
                             └─────────┬──────────┘
                                       │ 1:N
                                       ▼
                             ┌────────────────────┐
                             │   NetworkQuery     │
                             ├────────────────────┤
                             │ id (UUID, PK)      │
                             │ batch_id (FK)      │
                             │ codigo             │
                             │ tipo (poste/eqp)   │
                             │ status             │
                             │ raw_response       │
                             │ parsed_data (JSON) │
                             │ latitude           │
                             │ longitude          │
                             │ alimentador        │
                             │ response_ms        │
                             └────────────────────┘

  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
  │    Meter    │    │  KmlExport  │    │  AgentRun   │
  └─────────────┘    └─────────────┘    └─────────────┘
  (medidores)        (auditoria        (jobs de
                      de exports)       automação)
Migrations (Alembic)
bash


# Criar nova migration
alembic revision --autogenerate -m "descrição"

# Aplicar migrations
alembic upgrade head

# Reverter última
alembic downgrade -1

# Ver histórico
alembic history
🧪 Desenvolvimento
Smoke Tests Rápidos
bash


# 1) Importações OK?
python -c "from src.bot.application import create_dispatcher; print('✅')"

# 2) Worker compila?
python -c "from src.userbot.worker import worker_loop; print('✅')"

# 3) Exporters compilam?
python -c "from src.exporters import generate_bundle; print('✅')"

# 4) Pipeline completo?
python -c "
from src.bot.application import create_dispatcher
from src.userbot.worker import worker_loop
from src.exporters import generate_bundle
dp = create_dispatcher()
print(f'✅ {len(dp.sub_routers)} sub-routers ativos')
"
Logs Estruturados
O projeto usa structlog — logs em JSON em produção, coloridos em dev:

bash


# Filtrar logs do worker
python -m src.main 2>&1 | grep worker

# Logs em arquivo (produção)
python -m src.main 2>&1 | tee logs/bot.log
Estrutura de Testes Manuais
bash


# Sobe o bot
python -m src.main

# No Telegram:
/start           # menu inicial
/whoami          # confirma autorização
/status          # estado da fila
12345            # envia código direto após /start
📊 Roadmap
✅ Concluído
 µ1 — Bootstrap do projeto (aiogram + Telethon)
 µ2 — Banco com SQLAlchemy 2.0 async
 µ3 — Fila de consultas + worker
 µ4 — Parser de respostas do @ReincidenciasBot
 µ5 — Handlers /start, /help, /status, /whoami
 µ6 — Fluxo POSTE e EQUIPAMENTO
 µ7 — Persistência completa de lotes e queries
 µ8 — Exportação KML + CSV 📍
 Bloco 1: Exporters (KML agrupado por alimentador + CSV BR)
 Bloco 2: Handler /kml + botão inline
 Bloco 3: Notificação automática de conclusão
🔄 Em Backlog
 µ9 — Polimento UX: distinguir "não cadastrado" de sucesso
 µ10 — Comando /grant e /revoke para admins
 µ11 — Histórico de lotes (/historico)
 µ12 — Dashboard web (FastAPI + HTMX)
 µ13 — Migração SQLite → PostgreSQL em produção
 µ14 — Dockerfile + docker-compose
 µ15 — CI/CD (GitHub Actions)
 µ16 — Testes automatizados (pytest)
🛠️ Stack Técnica
Core



Lib	Versão	Função
aiogram	3.28.2	Framework para o bot Telegram
telethon	1.43.2	Cliente userbot
SQLAlchemy	2.0.49	ORM async
aiosqlite	0.22.1	Driver SQLite async (dev)
asyncpg	0.30.0	Driver PostgreSQL async (prod)
alembic	1.13.3	Migrations
pydantic	2.13.4	Validação de dados
pydantic-settings	2.14.1	Carregamento de .env
Exportação & Parsing



Lib	Versão	Função
simplekml	1.3.6	Geração de KML
lxml	5.3.0	Parser XML rápido
API & Infraestrutura



Lib	Versão	Função
FastAPI	0.115.0	API REST
uvicorn	0.32.0	Servidor ASGI
httpx	0.27.2	Cliente HTTP async
structlog	25.5.0	Logs estruturados
aiofiles	24.1.0	I/O async em arquivos
🧭 Troubleshooting
❌ ModuleNotFoundError: No module named 'src...'
bash


# Solução: execute como módulo, não como script
python -m src.main         # ✅ correto
python src/main.py         # ❌ errado
❌ Telethon pede código toda vez que sobe o bot
A sessão não está sendo persistida. Verifique:

A pasta data/ existe e tem permissão de escrita
O arquivo data/userbot.session foi criado após o primeiro login
❌ @ReincidenciasBot não responde
bash


# Verifique se o userbot tem o bot terceiro no histórico
# Abra o Telegram com a conta do userbot e mande /start manualmente para o bot terceiro
❌ KML não abre no Google Earth
Certifique-se de ter coordenadas válidas (lat ≠ 0, lng ≠ 0)
Tente abrir no Google Earth Web (https://earth.google.com)
Valide o XML: xmllint --noout exports/lote_XXX.kml
❌ Lote fica travado em "queued"
bash


# O worker pode ter caído. Veja os logs:
grep -i "worker" logs/bot.log | tail -50

# Reinicie o bot:
# Ctrl+C e python -m src.main
📜 Licença
Projeto proprietário — uso interno DPL Construções. Distribuição, cópia ou uso externo requer autorização expressa.

👥 Créditos
Desenvolvimento: Josué Santos
Assistência arquitetural: ARIA-BUILDER (metodologia µ-tasks)
Cliente: DPL Construções — Terceirizada
⚡ Bot Integrador DPL · Construído com ❤️ e ☕ em Imperatriz/MA

🔝 Voltar ao topo
