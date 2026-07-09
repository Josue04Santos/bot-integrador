"""
Diagnóstico do @ReincidenciasBot — observa e loga todo o fluxo conversacional.

Uso:
    python -m scripts.debug_bot_externo

O script:
  1. Conecta como userbot
  2. Registra TUDO que o bot externo envia (com timestamp e tamanho)
  3. Executa o fluxo passo a passo com delays configuráveis
  4. Gera relatório final do comportamento observado

Edite CODIGOS_TESTE abaixo antes de rodar.
"""
import asyncio
import time
from datetime import datetime, timezone

from telethon import TelegramClient, events
from telethon.sessions import StringSession
import sqlalchemy as sa

from src.config import settings
from src.database.connection import db
from src.utils.logger import setup_logging

# ── Configure os códigos para teste ────────────────────────────────────────
CODIGOS_POSTE = []

CODIGOS_EQUIPAMENTO = [
    "0907855",
]

# Delays (segundos) — ajuste para testar diferentes cenários
DELAY_APOS_COMANDO = 3.0   # tempo máximo aguardando o prompt do bot
DELAY_APOS_CODIGO  = 8.0   # tempo máximo aguardando a resposta do bot
DELAY_ENTRE_CONSULTAS = 2.0  # pausa entre cada consulta


# ── Observador passivo ──────────────────────────────────────────────────────
received_log: list[dict] = []


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def _log_recv(msg: str, label: str = "BOT_EXTERNO"):
    entry = {"ts": _ts(), "label": label, "len": len(msg), "text": msg}
    received_log.append(entry)
    print(f"\n{'='*60}")
    print(f"[{entry['ts']}] ← {label} ({entry['len']} chars)")
    print(f"{'='*60}")
    print(msg)
    print(f"{'='*60}")


async def _flush_queue(queue: asyncio.Queue, wait: float = 1.5) -> list[str]:
    """Coleta todas as mensagens disponíveis na fila até o timeout."""
    msgs = []
    deadline = time.monotonic() + wait
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            msg = await asyncio.wait_for(queue.get(), timeout=remaining)
            msgs.append(msg)
            deadline = time.monotonic() + 1.0  # estende 1s após cada msg
        except asyncio.TimeoutError:
            break
    return msgs


async def run_diagnostic():
    setup_logging()
    await db.initialize()

    # Carrega sessão do Postgres
    async with db.session() as session:
        result = await session.execute(sa.text(
            "SELECT session_data FROM telethon_sessions WHERE session_id = 'userbot'"
        ))
        row = result.first()
        session_str = row[0] if row else ""

    client = TelegramClient(
        StringSession(session_str),
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )

    queue: asyncio.Queue = asyncio.Queue()

    @client.on(events.NewMessage(
        from_users=settings.bot_terceiro_username,
        incoming=True,
    ))
    async def on_msg(event):
        text = event.message.text or ""
        if len(text) > 1:
            _log_recv(text)
            await queue.put(text)

    await client.start(phone=settings.telegram_phone)
    me = await client.get_me()
    print(f"\n✅ Userbot conectado: {me.first_name}")
    print(f"🎯 Bot alvo: @{settings.bot_terceiro_username}")
    print(f"\n{'#'*60}")
    print("INICIANDO DIAGNÓSTICO")
    print(f"{'#'*60}\n")

    resultados = []

    async def consultar(comando: str, codigo: str) -> dict:
        tipo = "POSTE" if "PTE" in comando else "EQUIPAMENTO"
        print(f"\n{'─'*60}")
        print(f"🔍 Testando {tipo}: {codigo}")
        print(f"{'─'*60}")

        # Limpa fila antes
        await asyncio.sleep(0.8)
        while not queue.empty():
            descartado = queue.get_nowait()
            print(f"  [descartado da fila] {str(descartado)[:60]}")

        resultado = {
            "codigo": codigo,
            "tipo": tipo,
            "comando": comando,
            "etapas": [],
        }

        # ETAPA 1: Envia comando
        t0 = time.monotonic()
        print(f"\n  → Enviando comando: {comando}")
        await client.send_message(settings.bot_terceiro_username, comando)

        # Aguarda prompt
        prompts = await _flush_queue(queue, wait=DELAY_APOS_COMANDO)
        t1 = time.monotonic()
        resultado["etapas"].append({
            "etapa": "aguarda_prompt",
            "msgs_recebidas": len(prompts),
            "tempo_s": round(t1 - t0, 2),
            "textos": prompts,
        })

        if not prompts:
            print(f"  ⚠️  NENHUM PROMPT recebido em {DELAY_APOS_COMANDO}s")
            resultado["status"] = "timeout_prompt"
            resultados.append(resultado)
            return resultado

        print(f"\n  ✅ Prompt recebido em {t1-t0:.2f}s ({len(prompts)} msg(s))")

        # ETAPA 2: Envia código
        t2 = time.monotonic()
        print(f"\n  → Enviando código: {codigo}")
        await client.send_message(settings.bot_terceiro_username, codigo)

        # Aguarda resposta
        respostas = await _flush_queue(queue, wait=DELAY_APOS_CODIGO)
        t3 = time.monotonic()
        resultado["etapas"].append({
            "etapa": "aguarda_resposta",
            "msgs_recebidas": len(respostas),
            "tempo_s": round(t3 - t2, 2),
            "textos": respostas,
        })

        if not respostas:
            print(f"  ⚠️  NENHUMA RESPOSTA recebida em {DELAY_APOS_CODIGO}s")
            resultado["status"] = "timeout_resposta"
        else:
            full = "\n".join(respostas)
            print(f"\n  ✅ Resposta em {t3-t2:.2f}s ({len(respostas)} msg(s), {len(full)} chars)")
            resultado["status"] = "ok"
            resultado["resposta_completa"] = full

        resultados.append(resultado)
        return resultado

    # Roda postes
    for cod in CODIGOS_POSTE:
        await consultar("/PTE", cod)
        await asyncio.sleep(DELAY_ENTRE_CONSULTAS)

    # Roda equipamentos
    for cod in CODIGOS_EQUIPAMENTO:
        await consultar("/EQP", cod)
        await asyncio.sleep(DELAY_ENTRE_CONSULTAS)

    # ── Relatório Final ─────────────────────────────────────────────────────
    print(f"\n\n{'#'*60}")
    print("RELATÓRIO FINAL")
    print(f"{'#'*60}")

    for r in resultados:
        print(f"\n[{r['tipo']}] {r['codigo']} → status: {r['status']}")
        for etapa in r["etapas"]:
            n = etapa["msgs_recebidas"]
            t = etapa["tempo_s"]
            print(f"  {etapa['etapa']}: {n} msg(s) em {t}s")
            for txt in etapa["textos"]:
                preview = txt[:80].replace("\n", " ")
                print(f"    » {preview}{'…' if len(txt)>80 else ''}")

    print(f"\n{'#'*60}")
    print(f"Total de mensagens do bot externo: {len(received_log)}")
    print(f"{'#'*60}\n")

    await client.disconnect()
    await db.close()


if __name__ == "__main__":
    if not CODIGOS_POSTE and not CODIGOS_EQUIPAMENTO:
        print("⚠️  Configure CODIGOS_POSTE e/ou CODIGOS_EQUIPAMENTO no topo do script!")
    else:
        asyncio.run(run_diagnostic())
