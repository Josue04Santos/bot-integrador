"""
Handler de exportação de lotes (KML + CSV).

Aciona-se por:
  • Comando  /kml <batch_id>            (manual, qualquer momento)
  • Callback "kml:<batch_id>"           (botão pós-conclusão)
"""

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import select

from src.bot.keyboards.export import CB_KML_PREFIX
from src.database.connection import db
from src.database.models import QueryBatch
from src.exporters import generate_bundle
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = Router(name="export")


# ============================================================
# Lógica compartilhada
# ============================================================
async def _resolve_batch_id(raw: str) -> str | None:
    """
    Aceita batch_id completo OU prefixo curto (#abc12345).
    Retorna o UUID completo ou None se não achar.
    """
    raw = raw.strip().lstrip("#")
    if not raw:
        return None

    async with db.session() as s:
        # Match exato primeiro
        q = select(QueryBatch).where(QueryBatch.id == raw)
        r = await s.execute(q)
        b = r.scalar_one_or_none()
        if b:
            return b.id

        # Match por prefixo (mínimo 6 chars pra evitar ambiguidade)
        if len(raw) >= 6:
            q = select(QueryBatch).where(QueryBatch.id.like(f"{raw}%"))
            r = await s.execute(q)
            results = r.scalars().all()
            if len(results) == 1:
                return results[0].id
            if len(results) > 1:
                return "AMBIGUOUS"

    return None


async def _send_bundle(message: Message, batch_id: str) -> None:
    """
    Gera e envia o pacote KML + GPX + CSV otimizados (µ9).
    """
    progress = await message.answer("⏳ <i>Otimizando rota (µ9)...</i>")

    try:
        bundle = await generate_bundle(batch_id)
    except ValueError as e:
        await progress.edit_text(f"❌ {e}")
        return
    except Exception as e:
        logger.exception("Falha ao gerar bundle", batch_id=batch_id)
        await progress.edit_text(f"❌ Erro ao gerar arquivos: <code>{e}</code>")
        return

    if bundle is None:
        await progress.edit_text(f"❌ Lote não encontrado: <code>{batch_id[:8]}</code>")
        return

    if bundle.total == 0:
        await progress.edit_text("⚠️ Este lote não tem respostas ainda.")
        return

    # ═══ Caption do KML (com stats da otimização) ═══
    caption_parts = [
        f"📦 <b>Lote</b> <code>#{batch_id[:8]}</code>",
        f"📊 Total: <b>{bundle.total}</b> ({bundle.total_postes} postes, {bundle.total_equipamentos} equipamentos)",
        f"✅ Com coordenadas: <b>{bundle.com_coords}</b>",
        f"⚠️ Sem coordenadas: <b>{bundle.sem_coords}</b>",
    ]

    if bundle.optimization:
        opt = bundle.optimization
        caption_parts.append("")
        caption_parts.append("🛣️ <b>Rota Otimizada (µ9)</b>")
        caption_parts.append(f"📏 Natural: <code>{opt.natural_km:.2f} km</code>")
        caption_parts.append(f"⚡ Otimizada: <code>{opt.otimizada_km:.2f} km</code>")
        caption_parts.append(f"💰 Economia: <b>{opt.economia_pct:.1f}%</b>")
        caption_parts.append(f"⏱️ Tempo: <code>{opt.tempo_ms:.0f} ms</code>")

    caption = "\n".join(caption_parts)

    await progress.edit_text("📤 <i>Enviando arquivos...</i>")

    # 1. KML (com caption rica)
    await message.answer_document(
        BufferedInputFile(bundle.kml_bytes, filename=f"{bundle.filename_base}.kml"),
        caption=caption,
    )

    # 2. GPX POSTES (nativo do OsmAnd)
    if bundle.gpx_bytes:
        await message.answer_document(
            BufferedInputFile(bundle.gpx_bytes, filename=f"{bundle.filename_base}_postes.gpx"),
            caption="📲 <i>Postes com rota otimizada (OsmAnd, Organic Maps, Google Earth)</i>",
        )

    # 2b. GPX EQUIPAMENTOS (waypoints)
    if bundle.gpx_equipamentos_bytes:
        await message.answer_document(
            BufferedInputFile(bundle.gpx_equipamentos_bytes, filename=f"{bundle.filename_base}_equipamentos.gpx"),
            caption="⚡ <i>Equipamentos/Instalações para inspeção (OsmAnd, Organic Maps, Google Earth)</i>",
        )

    # 3. CSV POSTES
    if bundle.total_postes > 0:
        await message.answer_document(
            BufferedInputFile(bundle.csv_postes_bytes, filename=f"{bundle.filename_base}_postes.csv"),
            caption="🏗️ <i>Dados de postes (Power BI / Excel)</i>",
        )

    # 4. CSV EQUIPAMENTOS
    if bundle.total_equipamentos > 0:
        await message.answer_document(
            BufferedInputFile(bundle.csv_equipamentos_bytes, filename=f"{bundle.filename_base}_equipamentos.csv"),
            caption="⚡ <i>Dados de equipamentos (use poste_referencia para cross-reference)</i>",
        )

    # 5. TXT de inválidos (só se houver)
    if bundle.invalidos_txt:
        await message.answer_document(
            BufferedInputFile(
                bundle.invalidos_txt.encode("utf-8"),
                filename=f"{bundle.filename_base}_invalidos.txt",
            ),
        )

    try:
        await progress.delete()
    except Exception:
        pass

    logger.info(
        "Bundle enviado",
        batch_id=batch_id[:8],
        total=bundle.total,
        postes=bundle.total_postes,
        equipamentos=bundle.total_equipamentos,
        com_coords=bundle.com_coords,
        otimizou=bundle.optimization is not None,
    )


# ============================================================
# Comando: /kml <batch_id>
# ============================================================
@router.message(Command("kml"))
async def cmd_kml(message: Message, command: CommandObject) -> None:
    """Permite baixar KML/CSV de qualquer lote pelo ID (ou prefixo de 6+ chars)."""
    if not command.args:
        await message.answer(
            "ℹ️ <b>Uso:</b> <code>/kml &lt;batch_id&gt;</code>\n\n"
            "Você pode usar o ID completo ou o prefixo curto:\n"
            "Ex.: <code>/kml 019e4d26</code>\n\n"
            "<i>O ID aparece como #xxxxxxxx na mensagem 'Lote enfileirado'.</i>"
        )
        return

    resolved = await _resolve_batch_id(command.args)

    if resolved is None:
        await message.answer(
            f"❌ Lote não encontrado: <code>{command.args}</code>"
        )
        return

    if resolved == "AMBIGUOUS":
        await message.answer(
            f"⚠️ Prefixo ambíguo: <code>{command.args}</code>\n"
            "Use mais caracteres para identificar o lote."
        )
        return

    await _send_bundle(message, resolved)


# ============================================================
# Callback: botão "📍 Baixar KML"
# ============================================================
@router.callback_query(F.data.startswith(f"{CB_KML_PREFIX}:"))
async def cb_kml_download(query: CallbackQuery) -> None:
    """Trata clique no botão de download anexado às mensagens de conclusão."""
    await query.answer("⏳ Gerando arquivos...")

    if not query.data or not query.message:
        return

    batch_id = query.data.split(":", 1)[1]

    # desabilita o botão para evitar cliques duplicados
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await _send_bundle(query.message, batch_id)
