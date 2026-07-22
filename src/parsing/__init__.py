"""Parsers de respostas do @ReincidenciasBot — poste e equipamento."""
from src.parsing.deteccao import is_not_found
from src.parsing.equipamento import ComponenteResultado, EquipamentoResultado, parse_equipamento
from src.parsing.poste import PosteResultado, parse_poste

__all__ = [
    "is_not_found",
    "parse_poste",
    "PosteResultado",
    "parse_equipamento",
    "EquipamentoResultado",
    "ComponenteResultado",
]
