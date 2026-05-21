"""
Parser para extrair dados das respostas do @ReincidenciasBot.
"""

import re
from typing import Optional, Union

from src.models.schemas import (
    Coordenadas,
    PosteData,
    InstalacaoData,
    ChaveMontante,
    TipoEquipamento,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ResponseParser:
    """
    Parser para extrair dados estruturados das respostas do bot de terceiros.
    
    Suporta 3 tipos de resposta:
    - Poste com estruturas MT/BT
    - Instalação (Transformador/Chave)
    - Poste simples (apenas BT)
    """
    
    # Regex patterns
    COORD_PATTERN = re.compile(
        r'(-?\d+\.?\d*),\s*(-?\d+\.?\d*)\s*\(http',
        re.IGNORECASE
    )
    
    COORD_URL_PATTERN = re.compile(
        r'maps/place/(-?\d+\.?\d*),(-?\d+\.?\d*)',
        re.IGNORECASE
    )
    
    POSTE_PATTERN = re.compile(r'Poste:\s*(\d+)', re.IGNORECASE)
    INSTALACAO_PATTERN = re.compile(r'Instalação:\s*(\d+)', re.IGNORECASE)
    ALIMENTADOR_PATTERN = re.compile(r'Alimentador[:\s]+([A-Z0-9\-]+)', re.IGNORECASE)
    CABO_PATTERN = re.compile(r'Cabo\s+(.+?)(?:\[|\n|$)', re.IGNORECASE)
    
    # Patterns para estruturas MT/BT
    MT_PATTERN = re.compile(r'MT:\s*(.+?)(?=BT:|Alimentador|Localização|$)', re.DOTALL | re.IGNORECASE)
    BT_PATTERN = re.compile(r'BT:\s*(.+?)(?=MT:|Alimentador|Localização|$)', re.DOTALL | re.IGNORECASE)
    NIVEL_PATTERN = re.compile(r'\[nivel\s+\d+\s+(.+?)\s*\]', re.IGNORECASE)
    
    # Patterns para Instalação
    PERIMETRO_PATTERN = re.compile(r'Perímetro:\s*(\w+)', re.IGNORECASE)
    TIPO_PATTERN = re.compile(r'Tipo:\s*(.+?)(?:\n|$)', re.IGNORECASE)
    POTENCIA_PATTERN = re.compile(r'Potência:\s*(.+?)(?:\n|$)', re.IGNORECASE)
    TENSAO_PRIM_PATTERN = re.compile(r'Tensão Primária:\s*(.+?)(?:\n|$)', re.IGNORECASE)
    TENSAO_SEC_PATTERN = re.compile(r'Tensão Secundária:\s*(.+?)(?:\n|$)', re.IGNORECASE)
    FASE_PATTERN = re.compile(r'Fase:\s*(\w+)', re.IGNORECASE)
    CLIENTES_PATTERN = re.compile(r'Clientes:\s*(\d+)', re.IGNORECASE)
    SITUACAO_PATTERN = re.compile(r'Situação:\s*(\w+)', re.IGNORECASE)
    
    # Pattern para chaves a montante
    CHAVE_LINE_PATTERN = re.compile(
        r'(FU|CF|RG|DJ|SE)\s+(\w+)\s+(\w+)?\s*(\d+)\s+(\d+)\s*(.*)?',
        re.IGNORECASE
    )

    @classmethod
    def detect_type(cls, text: str) -> TipoEquipamento:
        """Detecta o tipo de equipamento na resposta."""
        if cls.INSTALACAO_PATTERN.search(text):
            return TipoEquipamento.INSTALACAO
        if cls.POSTE_PATTERN.search(text):
            return TipoEquipamento.POSTE
        return TipoEquipamento.DESCONHECIDO

    @classmethod
    def parse(cls, text: str) -> Optional[Union[PosteData, InstalacaoData]]:
        """
        Faz o parse da resposta e retorna o objeto apropriado.
        
        Args:
            text: Texto da resposta do bot
            
        Returns:
            PosteData ou InstalacaoData, ou None se não reconhecido
        """
        tipo = cls.detect_type(text)
        
        if tipo == TipoEquipamento.INSTALACAO:
            return cls._parse_instalacao(text)
        elif tipo == TipoEquipamento.POSTE:
            return cls._parse_poste(text)
        else:
            logger.warning(f"Tipo de resposta não reconhecido: {text[:100]}...")
            return None

    @classmethod
    def _extract_coordenadas(cls, text: str) -> Optional[Coordenadas]:
        """Extrai coordenadas da resposta."""
        # Tenta primeiro o padrão com link
        match = cls.COORD_PATTERN.search(text)
        if match:
            try:
                lat = float(match.group(1))
                lon = float(match.group(2))
                return Coordenadas(latitude=lat, longitude=lon)
            except ValueError:
                pass
        
        # Tenta extrair da URL do maps
        match = cls.COORD_URL_PATTERN.search(text)
        if match:
            try:
                lat = float(match.group(1))
                lon = float(match.group(2))
                return Coordenadas(latitude=lat, longitude=lon)
            except ValueError:
                pass
        
        return None

    @classmethod
    def _extract_estruturas(cls, text: str, pattern: re.Pattern) -> list[str]:
        """Extrai estruturas (MT ou BT) da resposta."""
        match = pattern.search(text)
        if not match:
            return []
        
        estruturas_text = match.group(1)
        niveis = cls.NIVEL_PATTERN.findall(estruturas_text)
        return niveis

    @classmethod
    def _parse_poste(cls, text: str) -> Optional[PosteData]:
        """Parse de resposta de Poste."""
        match = cls.POSTE_PATTERN.search(text)
        if not match:
            return None
        
        codigo = match.group(1)
        
        # Extrai estruturas MT e BT
        estruturas_mt = cls._extract_estruturas(text, cls.MT_PATTERN)
        estruturas_bt = cls._extract_estruturas(text, cls.BT_PATTERN)
        
        # Extrai alimentador
        alimentador_match = cls.ALIMENTADOR_PATTERN.search(text)
        alimentador = alimentador_match.group(1) if alimentador_match else None
        
        # Extrai cabos
        cabos = cls.CABO_PATTERN.findall(text)
        cabos = [cabo.strip() for cabo in cabos]
        
        # Extrai coordenadas
        coordenadas = cls._extract_coordenadas(text)
        
        return PosteData(
            codigo=codigo,
            estruturas_mt=estruturas_mt,
            estruturas_bt=estruturas_bt,
            alimentador=alimentador,
            cabos=cabos,
            coordenadas=coordenadas,
            raw_response=text,
        )

    @classmethod
    def _parse_instalacao(cls, text: str) -> Optional[InstalacaoData]:
        """Parse de resposta de Instalação."""
        match = cls.INSTALACAO_PATTERN.search(text)
        if not match:
            return None
        
        codigo = match.group(1)
        
        # Extrai campos básicos
        def extract_field(pattern: re.Pattern) -> Optional[str]:
            m = pattern.search(text)
            if m:
                value = m.group(1).strip()
                return value if value and value.lower() != "não informada" else None
            return None
        
        alimentador = extract_field(cls.ALIMENTADOR_PATTERN)
        perimetro = extract_field(cls.PERIMETRO_PATTERN)
        tipo = extract_field(cls.TIPO_PATTERN)
        potencia = extract_field(cls.POTENCIA_PATTERN)
        tensao_primaria = extract_field(cls.TENSAO_PRIM_PATTERN)
        tensao_secundaria = extract_field(cls.TENSAO_SEC_PATTERN)
        fase = extract_field(cls.FASE_PATTERN)
        situacao = extract_field(cls.SITUACAO_PATTERN)
        
        # Extrai poste
        poste_match = cls.POSTE_PATTERN.search(text)
        poste = poste_match.group(1) if poste_match else None
        
        # Extrai clientes
        clientes_match = cls.CLIENTES_PATTERN.search(text)
        clientes = int(clientes_match.group(1)) if clientes_match else None
        
        # Extrai chaves a montante
        chaves_montante = cls._parse_chaves_montante(text)
        
        # Extrai coordenadas
        coordenadas = cls._extract_coordenadas(text)
        
        return InstalacaoData(
            codigo=codigo,
            alimentador=alimentador,
            perimetro=perimetro,
            tipo=tipo,
            poste=poste,
            potencia=potencia,
            tensao_primaria=tensao_primaria,
            tensao_secundaria=tensao_secundaria,
            fase=fase,
            clientes=clientes,
            situacao=situacao,
            chaves_montante=chaves_montante,
            coordenadas=coordenadas,
            raw_response=text,
        )

    @classmethod
    def _parse_chaves_montante(cls, text: str) -> list[ChaveMontante]:
        """Extrai tabela de chaves a montante."""
        chaves = []
        
        # Encontra a seção de chaves
        if "CHAVES A MONTANTE" not in text.upper():
            return chaves
        
        # Processa linha por linha após o cabeçalho
        lines = text.split('\n')
        in_table = False
        
        for line in lines:
            line = line.strip()
            
            # Detecta início/fim da tabela
            if "-----" in line:
                in_table = not in_table
                continue
            
            if not in_table or not line:
                continue
            
            # Parse da linha de chave
            # Formato: FU  1413228       6K       222         1
            parts = line.split()
            if len(parts) >= 4:
                try:
                    componente = parts[0]  # FU, CF, RG, DJ, SE
                    codigo = parts[1]
                    
                    # Detecta se tem elo (6K, 10K, etc)
                    elo = None
                    idx = 2
                    if parts[2].upper().endswith('K') or parts[2].upper() == 'LAM':
                        elo = parts[2]
                        idx = 3
                    
                    clientes = int(parts[idx]) if idx < len(parts) else 0
                    trafos = int(parts[idx + 1]) if idx + 1 < len(parts) else 0
                    
                    # Observação (ex: "Religadora")
                    observacao = None
                    if idx + 2 < len(parts):
                        observacao = ' '.join(parts[idx + 2:])
                    
                    chaves.append(ChaveMontante(
                        componente=componente,
                        codigo=codigo,
                        elo=elo,
                        clientes=clientes,
                        trafos=trafos,
                        observacao=observacao if observacao else None,
                    ))
                except (ValueError, IndexError) as e:
                    logger.debug(f"Erro ao parsear linha de chave: {line} - {e}")
                    continue
        
        return chaves
