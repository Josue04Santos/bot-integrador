"""
Detecção de respostas "não encontrado" do @ReincidenciasBot.

Único lugar do sistema que sabe reconhecer essas frases — reaproveitado
tanto pelo worker do bot (fluxo em tempo real) quanto pelos parsers novos
(src/parsing/poste.py, src/parsing/equipamento.py), pra nunca duplicar a
lista e correr o risco dela divergir entre os dois usos.
"""

NAO_CADASTRADO_PATTERNS = (
    "não cadastrado",
    "nao cadastrado",
    "não encontrado",
    "nao encontrado",
    "código inválido",
    "codigo invalido",
    "não existe",
    "nao existe",
    "comando não reconhecido",
    "comando nao reconhecido",
    "favor refazer o processo",
)


def is_not_found(raw: str) -> bool:
    """True se o texto bruto indica que o código não está cadastrado no bot terceiro."""
    lower = raw.lower()
    return any(p in lower for p in NAO_CADASTRADO_PATTERNS)
