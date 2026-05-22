"""
Serviços de domínio.

⚠️ Conteúdo legado removido em refatoração:
   - kml_generator.py → migrado para src/exporters/
   - query_processor.py → não utilizado
"""
from .parser import ResponseParser

__all__ = ["ResponseParser"]
