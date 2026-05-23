"""
Handlers para comandos administrativos.
"""

import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from src.config import settings
from src.database.connection import db
from src.database.models import AuthorizedUser, utcnow

router = Router(name="admin")
logger = structlog.get_logger(__name__)


def is_super_admin(telegram_id: int) -> bool:
    """Verifica se o usuário é super admin."""
    return telegram_id in settings.super_admin_ids


@router.message(Command("autorizar"))
async def cmd_autorizar(message: Message):
    """
    Autoriza um novo usuário no sistema.
    Uso: /autorizar <telegram_id> [nome completo]
    Restrito a super admins.
    """
    if not is_super_admin(message.from_user.id):
        await message.reply("⛔ Você não tem permissão para usar este comando.")
        return

    # Valida argumentos
    args = message.text.split()[1:] if message.text else []
    if not args:
        await message.reply(
            "❌ Uso incorreto.\n"
            "Formato: /autorizar <telegram_id> [nome completo]\n"
            "Exemplo: /autorizar 123456789 João Silva"
        )
        return

    try:
        target_id = int(args[0])
        full_name = " ".join(args[1:]) if len(args) > 1 else None
    except ValueError:
        await message.reply("❌ O telegram_id deve ser um número inteiro.")
        return

    # Usa o ORM correto
    async with db.session() as session:
        try:
            # Verifica se já existe
            stmt = select(AuthorizedUser).where(AuthorizedUser.tg_id == target_id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Reativa se estava inativo
                if not existing.active:
                    existing.active = True
                    existing.updated_at = utcnow()
                    await session.commit()
                    await message.reply(
                        f"✅ Usuário {target_id} reativado com sucesso!\n"
                        f"Nome: {existing.full_name or 'Não informado'}"
                    )
                else:
                    await message.reply(
                        f"ℹ️ Usuário {target_id} já está cadastrado e ativo.\n"
                        f"Nome: {existing.full_name or 'Não informado'}"
                    )
                return

            # Cria novo usuário
            new_user = AuthorizedUser(
                tg_id=target_id,
                full_name=full_name,
                role="user",
                active=True,
                last_seen_at=utcnow()
            )
            session.add(new_user)
            await session.commit()

            logger.info(
                "Usuário autorizado com sucesso",
                target_id=target_id,
                full_name=full_name,
                by_admin=message.from_user.id
            )

            await message.reply(
                f"✅ Usuário autorizado com sucesso!\n"
                f"📱 Telegram ID: <code>{target_id}</code>\n"
                f"👤 Nome: {full_name or 'Não informado'}\n"
                f"🔑 Role: user"
            )

        except Exception as e:
            await session.rollback()
            logger.error("Erro ao autorizar usuário", error=str(e), target_id=target_id)
            error_msg = str(e).replace('<', '').replace('>', '')
            await message.reply(f"❌ Erro ao autorizar usuário:\n{error_msg}")


@router.message(Command("desautorizar"))
async def cmd_desautorizar(message: Message):
    """
    Desativa um usuário do sistema.
    Uso: /desautorizar <telegram_id>
    Restrito a super admins.
    """
    if not is_super_admin(message.from_user.id):
        await message.reply("⛔ Você não tem permissão para usar este comando.")
        return

    args = message.text.split()[1:] if message.text else []
    if not args:
        await message.reply(
            "❌ Uso incorreto.\n"
            "Formato: /desautorizar <telegram_id>"
        )
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await message.reply("❌ O telegram_id deve ser um número inteiro.")
        return

    async with db.session() as session:
        try:
            stmt = select(AuthorizedUser).where(AuthorizedUser.tg_id == target_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                await message.reply(f"❌ Usuário {target_id} não encontrado.")
                return

            user.active = False
            user.updated_at = utcnow()
            await session.commit()

            logger.info(
                "Usuário desautorizado",
                target_id=target_id,
                by_admin=message.from_user.id
            )

            await message.reply(
                f"✅ Usuário {target_id} desativado com sucesso!\n"
                f"Nome: {user.full_name or 'Não informado'}"
            )

        except Exception as e:
            await session.rollback()
            logger.error("Erro ao desautorizar usuário", error=str(e))
            await message.reply(f"❌ Erro: {str(e)}")


@router.message(Command("usuarios"))
async def cmd_usuarios(message: Message):
    """
    Lista todos os usuários autorizados.
    Restrito a super admins.
    """
    if not is_super_admin(message.from_user.id):
        await message.reply("⛔ Você não tem permissão para usar este comando.")
        return

    async with db.session() as session:
        try:
            stmt = select(AuthorizedUser).order_by(AuthorizedUser.created_at.desc())
            result = await session.execute(stmt)
            users = result.scalars().all()

            if not users:
                await message.reply("ℹ️ Nenhum usuário cadastrado.")
                return

            # Formata resposta
            lines = ["📋 <b>Usuários Cadastrados</b>\n"]
            for user in users:
                status = "✅" if user.active else "⛔"
                role_icon = "👑" if user.role == "admin" else "👤"
                name = user.full_name or f"ID: {user.tg_id}"
                username = f"@{user.username}" if user.username else ""
                
                lines.append(
                    f"{status} {role_icon} <b>{name}</b> {username}\n"
                    f"   └ ID: <code>{user.tg_id}</code> | "
                    f"Role: {user.role} | "
                    f"Cadastro: {user.created_at.strftime('%d/%m/%Y')}"
                )

            await message.reply("\n\n".join(lines))

        except Exception as e:
            logger.error("Erro ao listar usuários", error=str(e))
            error_msg = str(e).replace('<', '').replace('>', '')
            await message.reply(f"❌ Erro ao listar usuários:\n{error_msg}")


@router.message(Command("promover"))
async def cmd_promover(message: Message):
    """
    Promove usuário para admin.
    Uso: /promover <telegram_id>
    Restrito a super admins.
    """
    if not is_super_admin(message.from_user.id):
        await message.reply("⛔ Você não tem permissão para usar este comando.")
        return

    args = message.text.split()[1:] if message.text else []
    if not args:
        await message.reply(
            "❌ Uso incorreto.\n"
            "Formato: /promover <telegram_id>"
        )
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await message.reply("❌ O telegram_id deve ser um número inteiro.")
        return

    async with db.session() as session:
        try:
            stmt = select(AuthorizedUser).where(AuthorizedUser.tg_id == target_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                await message.reply(f"❌ Usuário {target_id} não encontrado.")
                return

            if user.role == "admin":
                await message.reply(f"ℹ️ Usuário já é admin.")
                return

            user.role = "admin"
            user.updated_at = utcnow()
            await session.commit()

            logger.info(
                "Usuário promovido para admin",
                target_id=target_id,
                by_admin=message.from_user.id
            )

            await message.reply(
                f"✅ Usuário promovido para admin!\n"
                f"👤 {user.full_name or target_id}"
            )

        except Exception as e:
            await session.rollback()
            logger.error("Erro ao promover usuário", error=str(e))
            await message.reply(f"❌ Erro: {str(e)}")
