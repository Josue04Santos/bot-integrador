"""Teclados inline relacionados à exportação de lotes (KML/CSV)."""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


# Callback prefix
CB_KML_PREFIX = "kml"


def cb_kml_download(batch_id: str) -> str:
    """Monta callback_data para download de KML de um batch."""
    # Telegram limita callback_data a 64 bytes — UUIDs cabem (36 chars)
    return f"{CB_KML_PREFIX}:{batch_id}"


def kml_download_kb(batch_id: str) -> InlineKeyboardMarkup:
    """
    Botão único '📍 Baixar KML' para exibir após conclusão de lote.
    Também pode ser anexado a mensagens antigas via comando /kml.
    """
    kb = InlineKeyboardBuilder()
    kb.button(
        text="📍 Baixar KML + CSV",
        callback_data=cb_kml_download(batch_id),
    )
    return kb.as_markup()
