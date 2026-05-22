"""FSM para coleta de código(s) após escolha do tipo de consulta."""

from aiogram.fsm.state import State, StatesGroup


class QueryStates(StatesGroup):
    """Estados do fluxo de consulta."""
    waiting_code = State()   # aguardando texto ou arquivo .txt com códigos
