"""
Comandos administrativos pra lista de códigos "não cadastrado" (TTL 7 dias):
  /naocadastrados            — lista (só texto, sem botão)
  /excluirnaocadastrado <codigo> <poste|equipamento> — remove um da lista
"""
import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.bot.handlers.admin import is_super_admin
from src.database.connection import db
from src.services import nao_cadastrado_service

router = Router(name="nao_cadastrados")
logger = structlog.get_logger(__name__)


def _tipo_label(query_type: str) -> str:
    return "equipamento" if query_type == "instalacao" else "poste"


@router.message(Command("naocadastrados"))
async def cmd_listar_nao_cadastrados(message: Message) -> None:
    """Lista os últimos códigos confirmados como não cadastrados. Restrito a super admins."""
    if not is_super_admin(message.from_user.id):
        await message.reply("⛔ Você não tem permissão para usar este comando.")
        return

    async with db.session() as session:
        entries = await nao_cadastrado_service.listar(session, limit=20)

    if not entries:
        await message.reply("ℹ️ Nenhum código não cadastrado registrado.")
        return

    lines = ["📋 <b>Códigos não cadastrados</b> (TTL 7 dias, últimos 20)\n"]
    for e in entries:
        lines.append(
            f"• <code>{e.code}</code> ({_tipo_label(e.query_type)}) — "
            f"{e.vezes_confirmado}x, última vez {e.ultima_vez.strftime('%d/%m %H:%M')}"
        )
    lines.append("\n<i>Use /excluirnaocadastrado &lt;código&gt; &lt;poste|equipamento&gt; pra remover um.</i>")

    await message.reply("\n".join(lines))


@router.message(Command("excluirnaocadastrado"))
async def cmd_excluir_nao_cadastrado(message: Message) -> None:
    """
    Remove um código da lista de não cadastrados — força a próxima
    consulta a ir ao vivo, em vez de esperar o TTL de 7 dias vencer.
    Uso: /excluirnaocadastrado <codigo> <poste|equipamento>
    Restrito a super admins.
    """
    if not is_super_admin(message.from_user.id):
        await message.reply("⛔ Você não tem permissão para usar este comando.")
        return

    args = message.text.split()[1:] if message.text else []
    if len(args) != 2 or args[1] not in ("poste", "equipamento"):
        await message.reply(
            "❌ Uso incorreto.\n"
            "Formato: /excluirnaocadastrado <codigo> <poste|equipamento>\n"
            "Exemplo: /excluirnaocadastrado 2133830 equipamento"
        )
        return

    codigo, tipo = args
    query_type = "instalacao" if tipo == "equipamento" else "poste"

    async with db.session() as session:
        removido = await nao_cadastrado_service.remover(session, codigo, query_type)

    if removido:
        logger.info(
            "Código removido da lista de não cadastrados",
            codigo=codigo, tipo=tipo, by_admin=message.from_user.id,
        )
        await message.reply(
            f"✅ Removido: <code>{codigo}</code> ({tipo})\n"
            f"A próxima consulta vai direto ao vivo de novo."
        )
    else:
        await message.reply(
            f"ℹ️ <code>{codigo}</code> ({tipo}) não estava na lista de não cadastrados."
        )
