"""Teclado principal do /start."""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


# Callback data padronizado: "query:<tipo>"
CB_QUERY_POSTE = "query:poste"
CB_QUERY_EQUIPAMENTO = "query:instalacao"
CB_CANCEL = "query:cancel"


def main_menu_kb() -> InlineKeyboardMarkup:
    """Botões iniciais do /start: escolher tipo de consulta."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🏗️ POSTE", callback_data=CB_QUERY_POSTE)
    kb.button(text="⚡ EQUIPAMENTO", callback_data=CB_QUERY_EQUIPAMENTO)
    kb.adjust(2)
    return kb.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    """Botão de cancelar durante coleta de código."""
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Cancelar", callback_data=CB_CANCEL)
    return kb.as_markup()
