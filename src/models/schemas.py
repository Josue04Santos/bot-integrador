"""
Schemas e modelos de dados para o Bot Integrador.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TipoEquipamento(Enum):
    """Tipos de equipamento que podem ser consultados."""
    POSTE = "poste"
    INSTALACAO = "instalacao"
    DESCONHECIDO = "desconhecido"


class ConsultaStatus(Enum):
    """Status de uma consulta."""
    PENDENTE = "pendente"
    ENVIADA = "enviada"
    RESPONDIDA = "respondida"
    TIMEOUT = "timeout"
    ERRO = "erro"


@dataclass
class Coordenadas:
    """Coordenadas geográficas."""
    latitude: float
    longitude: float
    
    @property
    def google_maps_url(self) -> str:
        """Retorna URL do Google Maps."""
        return f"https://www.google.com.br/maps/place/{self.latitude},{self.longitude}"
    
    @property
    def dms(self) -> str:
        """Retorna coordenadas em graus, minutos e segundos."""
        def to_dms(value: float, is_lat: bool) -> str:
            direction = ("S" if value < 0 else "N") if is_lat else ("W" if value < 0 else "E")
            value = abs(value)
            degrees = int(value)
            minutes = int((value - degrees) * 60)
            seconds = ((value - degrees) * 60 - minutes) * 60
            return f"{degrees}°{minutes:02d}'{seconds:05.2f}\"{direction}"
        
        return f"{to_dms(self.latitude, True)} {to_dms(self.longitude, False)}"


@dataclass
class ChaveMontante:
    """Representa uma chave a montante até a subestação."""
    componente: str          # Ex: "FU", "CF", "RG", "DJ"
    codigo: str              # Ex: "1413228"
    elo: Optional[str]       # Ex: "6K", "10K", "100K", "LAM"
    clientes: int
    trafos: int
    observacao: Optional[str] = None  # Ex: "Religadora"


@dataclass
class PosteData:
    """Dados de um Poste."""
    codigo: str
    estruturas_mt: list[str] = field(default_factory=list)
    estruturas_bt: list[str] = field(default_factory=list)
    alimentador: Optional[str] = None
    cabos: list[str] = field(default_factory=list)
    coordenadas: Optional[Coordenadas] = None
    raw_response: str = ""
    
    @property
    def tipo(self) -> TipoEquipamento:
        return TipoEquipamento.POSTE
    
    @property
    def tem_mt(self) -> bool:
        return len(self.estruturas_mt) > 0
    
    @property
    def tem_bt(self) -> bool:
        return len(self.estruturas_bt) > 0


@dataclass
class InstalacaoData:
    """Dados de uma Instalação (Transformador/Chave)."""
    codigo: str
    alimentador: Optional[str] = None
    perimetro: Optional[str] = None      # URBANO / RURAL
    tipo: Optional[str] = None           # Chave Fusível, etc.
    poste: Optional[str] = None
    potencia: Optional[str] = None       # Ex: "112,50kVA"
    tensao_primaria: Optional[str] = None
    tensao_secundaria: Optional[str] = None
    fase: Optional[str] = None           # ABC, AB, etc.
    clientes: Optional[int] = None
    situacao: Optional[str] = None       # OPERACAO
    chaves_montante: list[ChaveMontante] = field(default_factory=list)
    coordenadas: Optional[Coordenadas] = None
    raw_response: str = ""
    
    @property
    def tipo_equipamento(self) -> TipoEquipamento:
        return TipoEquipamento.INSTALACAO


@dataclass
class ConsultaResult:
    """Resultado de uma consulta."""
    codigo: str
    tipo: TipoEquipamento
    status: ConsultaStatus
    data: Optional[PosteData | InstalacaoData] = None
    erro: Optional[str] = None
    timestamp_envio: Optional[datetime] = None
    timestamp_resposta: Optional[datetime] = None
    
    @property
    def tempo_resposta(self) -> Optional[float]:
        """Tempo de resposta em segundos."""
        if self.timestamp_envio and self.timestamp_resposta:
            return (self.timestamp_resposta - self.timestamp_envio).total_seconds()
        return None
