"""Sistema de despacho assíncrono Bot DPL ↔ UserBot."""
from src.dispatcher.queue import query_queue, QueueItem

__all__ = ["query_queue", "QueueItem"]
