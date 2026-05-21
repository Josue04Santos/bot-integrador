"""
Middleware de logging para registrar todas as atualizações.
"""

import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from src.utils.logger import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """
    Middleware que loga todas as atualizações recebidas.
    Útil para debug e monitoramento.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        start_time = time.perf_counter()

        # Extrai informações do update
        update_info = self._extract_update_info(event)

        logger.debug(
            "Update recebido",
            **update_info,
        )

        try:
            result = await handler(event, data)

            elapsed = (time.perf_counter() - start_time) * 1000
            logger.info(
                "Update processado",
                elapsed_ms=round(elapsed, 2),
                **update_info,
            )

            return result

        except Exception as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.error(
                "Erro ao processar update",
                error=str(e),
                error_type=type(e).__name__,
                elapsed_ms=round(elapsed, 2),
                **update_info,
            )
            raise

    def _extract_update_info(self, event: TelegramObject) -> Dict[str, Any]:
        """Extrai informações relevantes do update."""
        info: Dict[str, Any] = {}

        if isinstance(event, Update):
            info["update_id"] = event.update_id

            if event.message:
                msg = event.message
                info["type"] = "message"
                info["chat_id"] = msg.chat.id
                info["chat_type"] = msg.chat.type
                info["user_id"] = msg.from_user.id if msg.from_user else None
                info["message_id"] = msg.message_id

                if msg.text:
                    # Limita o texto para não poluir logs
                    info["text_preview"] = msg.text[:50] + "..." if len(msg.text) > 50 else msg.text

            elif event.callback_query:
                cb = event.callback_query
                info["type"] = "callback_query"
                info["user_id"] = cb.from_user.id
                info["callback_data"] = cb.data

            elif event.channel_post:
                post = event.channel_post
                info["type"] = "channel_post"
                info["chat_id"] = post.chat.id
                info["message_id"] = post.message_id

            elif event.edited_message:
                info["type"] = "edited_message"

            elif event.inline_query:
                info["type"] = "inline_query"
                info["user_id"] = event.inline_query.from_user.id

            else:
                info["type"] = "other"

        return info
