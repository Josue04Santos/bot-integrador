"""
Configurações do Bot Integrador — ponto único de acesso.

⚠️ IMPORTANTE: Use sempre nomes em minúsculo (snake_case).
    settings.telegram_bot_token  ✅
    settings.TELEGRAM_BOT_TOKEN  ❌ (não mais suportado)
"""
from src.utils.config import Settings, get_settings

# Instância global única
settings: Settings = get_settings()

__all__ = ["settings", "Settings", "get_settings"]
