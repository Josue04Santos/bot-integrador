"""
Rota /conversa — monitor em tempo real da conversa bot-integrador ↔ bot-externo.
Lê os logs do systemd (journalctl) filtrando apenas eventos de conversa.
Não toca no serviço principal.
"""
import asyncio
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, StreamingResponse

router = APIRouter()

# Palavras-chave que identificam logs de conversa com o bot externo
_FILTROS = [
    "AGUARDA_PROMPT",
    "AGUARDA_RESPOSTA",
    "IDLE",
    "Prompt validado",
    "Mensagem inesperada",
    "Fila limpa",
    "Cadência",
    "Consulta concluída",
    "Enviando:",
    "Enviando código",
    "Resposta recebida",
    "Timeout",
    "Cache hit",
    "Cache stale",
    "Background refresh",
    "bot externo",
]


async def _ler_journal(n_linhas: int = 300) -> list[dict]:
    """Lê as últimas N linhas do journal filtrando logs de conversa."""
    proc = await asyncio.create_subprocess_exec(
        "journalctl", "-u", "bot-integrador",
        "-n", str(n_linhas),
        "--no-pager",
        "--output", "short-iso",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    linhas = stdout.decode("utf-8", errors="replace").splitlines()

    resultado = []
    for linha in linhas:
        if any(f in linha for f in _FILTROS):
            # Classifica o tipo para colorir no HTML
            if "AGUARDA_PROMPT" in linha:
                tipo = "prompt"
            elif "AGUARDA_RESPOSTA" in linha:
                tipo = "resposta"
            elif "IDLE" in linha:
                tipo = "idle"
            elif "Timeout" in linha or "timeout" in linha:
                tipo = "timeout"
            elif "Cache" in linha or "cache" in linha:
                tipo = "cache"
            elif "Cadência" in linha:
                tipo = "cadencia"
            elif "Mensagem inesperada" in linha or "Fila limpa" in linha:
                tipo = "aviso"
            else:
                tipo = "info"
            resultado.append({"linha": linha, "tipo": tipo})

    return list(reversed(resultado))


@router.get("/conversa", response_class=HTMLResponse)
async def conversa():
    logs = await _ler_journal(400)

    linhas_html = ""
    for entry in logs:
        cores = {
            "prompt":   "#38bdf8",   # azul
            "resposta": "#a78bfa",   # roxo
            "idle":     "#475569",   # cinza
            "timeout":  "#f87171",   # vermelho
            "cache":    "#22c55e",   # verde
            "cadencia": "#f59e0b",   # amarelo
            "aviso":    "#fb923c",   # laranja
            "info":     "#94a3b8",   # cinza claro
        }
        cor = cores.get(entry["tipo"], "#94a3b8")
        texto = entry["linha"].replace("<", "&lt;").replace(">", "&gt;")
        linhas_html += f'<div class="linha {entry["tipo"]}" style="color:{cor}">{texto}</div>\n'

    if not linhas_html:
        linhas_html = '<div class="linha info" style="color:#475569"><i>Nenhum log de conversa encontrado ainda. Inicie uma consulta no Telegram.</i></div>'

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="3">
<title>Conversa Bot ↔ Bot Externo</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Courier New', monospace; background: #0a0f1a; color: #e2e8f0; padding: 20px; font-size: 13px; }}
  h1 {{ font-size: 1.1rem; color: #38bdf8; margin-bottom: 8px; font-family: 'Segoe UI', sans-serif; }}
  .meta {{ font-size: .75rem; color: #475569; margin-bottom: 12px; font-family: 'Segoe UI', sans-serif; }}
  nav {{ display: flex; gap: 8px; margin-bottom: 16px; font-family: 'Segoe UI', sans-serif; }}
  nav a {{ display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: 8px; font-size: .85rem; text-decoration: none; background: #1e293b; color: #94a3b8; transition: background .15s; }}
  nav a:hover {{ background: #263347; color: #e2e8f0; }}
  nav a.active {{ background: #0ea5e9; color: #fff; }}
  .legenda {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 16px; font-size: .75rem; font-family: 'Segoe UI', sans-serif; }}
  .leg {{ padding: 3px 10px; border-radius: 4px; background: #1e293b; }}
  #log {{ background: #0f172a; border-radius: 8px; padding: 16px; overflow-x: auto; }}
  .linha {{ padding: 2px 0; line-height: 1.5; white-space: pre-wrap; word-break: break-all; border-bottom: 1px solid #0f172a; }}
  .linha:hover {{ background: #1e293b; }}
</style>
</head>
<body>
<h1>🤖 Bot Integrador</h1>
<nav>
  <a href="/historico">📋 Histórico de Lotes</a>
  <a href="/conversa" class="active">🔍 Conversa em Tempo Real</a>
</nav>
<p class="meta">Atualiza a cada 3s · {len(logs)} eventos encontrados · lendo journalctl</p>
<div class="legenda">
  <span class="leg" style="color:#38bdf8">■ Aguarda Prompt</span>
  <span class="leg" style="color:#a78bfa">■ Aguarda Resposta</span>
  <span class="leg" style="color:#22c55e">■ Cache</span>
  <span class="leg" style="color:#f59e0b">■ Cadência</span>
  <span class="leg" style="color:#f87171">■ Timeout</span>
  <span class="leg" style="color:#fb923c">■ Aviso</span>
  <span class="leg" style="color:#475569">■ IDLE</span>
</div>
<div id="log">
{linhas_html}
</div>
</body>
</html>""")
