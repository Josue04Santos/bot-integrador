"""
Rota /historico — visualização web dos lotes e consultas.
Acessível em: http://localhost:8001/historico
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from src.database.connection import db

router = APIRouter()


@router.get("/historico", response_class=HTMLResponse)
async def historico():
    async with db.session() as session:
        batches = await session.execute(text("""
            SELECT qb.id, qb.status, qb.total_codes, qb.success_count,
                   qb.failure_count, qb.timeout_count, qb.created_at,
                   EXTRACT(EPOCH FROM (qb.finished_at - qb.started_at))::int as dur,
                   au.full_name as usuario
            FROM query_batches qb
            LEFT JOIN authorized_users au ON au.id = qb.user_id
            ORDER BY qb.created_at DESC
            LIMIT 20
        """))
        batches = batches.fetchall()

        queries = await session.execute(text("""
            SELECT nq.batch_id, nq.code, nq.query_type, nq.status,
                   nq.response_ms, nq.error_message, nq.created_at,
                   LENGTH(nq.raw_response) as resp_len
            FROM network_queries nq
            WHERE nq.batch_id IN (
                SELECT id FROM query_batches ORDER BY created_at DESC LIMIT 20
            )
            ORDER BY nq.created_at
        """))
        queries = queries.fetchall()

    # Agrupa queries por batch
    qs_by_batch = {}
    for q in queries:
        qs_by_batch.setdefault(q.batch_id, []).append(q)

    # Gera HTML
    rows_batches = ""
    for b in batches:
        dur = f"{b.dur}s" if b.dur else "—"
        status_cor = {"completed": "#22c55e", "running": "#f59e0b", "failed": "#ef4444", "pending": "#94a3b8"}.get(b.status, "#94a3b8")
        taxa = round(b.success_count / b.total_codes * 100) if b.total_codes else 0

        rows_queries = ""
        for q in qs_by_batch.get(b.id, []):
            if q.response_ms == 0:
                tempo = '<span class="cache">📦 cache</span>'
            elif q.response_ms:
                tempo = f'<span class="bot">🌐 {q.response_ms}ms</span>'
            else:
                tempo = '<span class="timeout">⏱ —</span>'

            if q.status == "received":
                icone = "✅"
            elif q.status == "timeout":
                icone = "⏱"
            else:
                icone = "❌"

            tipo = "🏗️" if q.query_type == "poste" else "⚡"
            erro = q.error_message or ""
            resp = f"{q.resp_len or 0} chars" if q.resp_len else "—"

            rows_queries += f"""
            <tr>
                <td>{tipo} <code>{q.code}</code></td>
                <td>{icone} {q.status}</td>
                <td>{tempo}</td>
                <td>{resp}</td>
                <td class="erro">{erro}</td>
            </tr>"""

        rows_batches += f"""
        <div class="batch">
            <div class="batch-header" onclick="toggle('{b.id}')">
                <span style="color:{status_cor}">■</span>
                <code>#{b.id[:8]}</code>
                <span class="usuario">{b.usuario or '—'}</span>
                <span class="stats">{b.success_count}/{b.total_codes} OK · {b.failure_count} erros · {b.timeout_count} timeouts · {taxa}% · {dur}</span>
                <span class="data">{str(b.created_at)[:16]}</span>
            </div>
            <div class="batch-body" id="{b.id}" style="display:none">
                <table>
                    <thead><tr>
                        <th>Código</th><th>Status</th><th>Tempo</th><th>Resposta</th><th>Erro</th>
                    </tr></thead>
                    <tbody>{rows_queries}</tbody>
                </table>
            </div>
        </div>"""

    cache_count = await session.execute(text("SELECT COUNT(*) FROM code_cache"))
    cache_count = cache_count.scalar()

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="10">
<title>Bot Integrador — Histórico</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; padding: 24px; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 8px; color: #38bdf8; }}
  .meta {{ font-size: .8rem; color: #64748b; margin-bottom: 12px; }}
  nav {{ display: flex; gap: 8px; margin-bottom: 20px; }}
  nav a {{ display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: 8px; font-size: .85rem; text-decoration: none; background: #1e293b; color: #94a3b8; transition: background .15s; }}
  nav a:hover {{ background: #263347; color: #e2e8f0; }}
  nav a.active {{ background: #0ea5e9; color: #fff; }}
  .stats-bar {{ display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }}
  .stat {{ background: #1e293b; padding: 12px 20px; border-radius: 8px; font-size: .9rem; }}
  .stat b {{ display: block; font-size: 1.4rem; color: #38bdf8; }}
  .batch {{ background: #1e293b; border-radius: 8px; margin-bottom: 10px; overflow: hidden; }}
  .batch-header {{ padding: 12px 16px; cursor: pointer; display: flex; align-items: center; gap: 12px; font-size: .9rem; }}
  .batch-header:hover {{ background: #263347; }}
  .batch-header code {{ color: #94a3b8; font-size: .85rem; }}
  .usuario {{ color: #38bdf8; font-weight: 600; }}
  .stats {{ color: #94a3b8; font-size: .8rem; flex: 1; }}
  .data {{ color: #475569; font-size: .78rem; }}
  .batch-body {{ padding: 0 16px 16px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .85rem; }}
  th {{ text-align: left; padding: 8px; color: #64748b; border-bottom: 1px solid #334155; }}
  td {{ padding: 7px 8px; border-bottom: 1px solid #1e293b; }}
  tr:hover td {{ background: #263347; }}
  code {{ background: #0f172a; padding: 2px 6px; border-radius: 4px; font-size: .85rem; }}
  .cache {{ color: #22c55e; font-size: .8rem; }}
  .bot {{ color: #38bdf8; font-size: .8rem; }}
  .timeout {{ color: #f59e0b; font-size: .8rem; }}
  .erro {{ color: #f87171; font-size: .8rem; }}
</style>
</head>
<body>
<h1>🤖 Bot Integrador</h1>
<nav>
  <a href="/historico" class="active">📋 Histórico de Lotes</a>
  <a href="/conversa">🔍 Conversa em Tempo Real</a>
</nav>
<p class="meta">Atualiza automaticamente a cada 10s · {cache_count} códigos no cache</p>
<div class="stats-bar">
  <div class="stat"><b>{len(batches)}</b>lotes recentes</div>
  <div class="stat"><b>{cache_count}</b>no cache</div>
</div>
{rows_batches}
<script>
function toggle(id) {{
  var el = document.getElementById(id);
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}}
</script>
</body>
</html>""")
