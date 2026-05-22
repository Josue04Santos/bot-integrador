"""
Fila in-memory assíncrona ligando handlers do bot DPL ao worker do UserBot.

Por que asyncio.Queue?
- Mesmo processo Python, sem dependência externa (Redis/RabbitMQ)
- Backpressure automático (maxsize)
- Serialização natural (1 consulta por vez no UserBot)
"""

import asyncio
from dataclasses import dataclass

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class QueueItem:
    """Item enfileirado para processamento pelo worker."""
    query_id: str       # NetworkQuery.id
    batch_id: str       # QueryBatch.id (pra agrupar notificações)
    user_tg_id: int     # Telegram ID do usuário (pra notificar de volta)
    code: str           # código a consultar
    query_type: str     # "poste" | "instalacao"


class QueryQueue:
    """Wrapper sobre asyncio.Queue com logging integrado."""

    def __init__(self, maxsize: int = 1000):
        self._queue: asyncio.Queue[QueueItem] = asyncio.Queue(maxsize=maxsize)

    async def put(self, item: QueueItem) -> None:
        await self._queue.put(item)
        logger.info(
            "Query enfileirada",
            query_id=item.query_id[:8],
            code=item.code,
            type=item.query_type,
            qsize=self._queue.qsize(),
        )

    async def get(self) -> QueueItem:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()

    def size(self) -> int:
        return self._queue.qsize()


# Singleton compartilhado entre handlers e worker
query_queue = QueryQueue()
