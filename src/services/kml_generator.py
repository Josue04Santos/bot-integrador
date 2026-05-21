"""
Gerador de arquivos KML para Google Earth.
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Union
from xml.dom import minidom

from src.models.schemas import PosteData, InstalacaoData, TipoEquipamento
from src.utils.logger import get_logger

logger = get_logger(__name__)


class KMLGenerator:
    """
    Gera arquivos KML a partir dos dados extraídos.
    
    Suporta:
    - Postes (ícone diferenciado para MT/BT)
    - Instalações (ícone de transformador)
    - Lotes de equipamentos
    """
    
    # Estilos de ícones
    STYLES = {
        "poste_mt": {
            "icon": "http://maps.google.com/mapfiles/kml/shapes/electricity.png",
            "color": "ff0000ff",  # Vermelho
            "scale": 1.2,
        },
        "poste_bt": {
            "icon": "http://maps.google.com/mapfiles/kml/paddle/ylw-circle.png",
            "color": "ff00ffff",  # Amarelo
            "scale": 1.0,
        },
        "instalacao": {
            "icon": "http://maps.google.com/mapfiles/kml/shapes/ranger_station.png",
            "color": "ff00ff00",  # Verde
            "scale": 1.3,
        },
    }

    @classmethod
    def generate(
        cls,
        items: list[Union[PosteData, InstalacaoData]],
        filename: str = "equipamentos.kml",
        output_dir: str = "./output",
    ) -> Path:
        """
        Gera arquivo KML a partir de uma lista de equipamentos.
        
        Args:
            items: Lista de PosteData ou InstalacaoData
            filename: Nome do arquivo de saída
            output_dir: Diretório de saída
            
        Returns:
            Path do arquivo gerado
        """
        # Cria diretório se não existir
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Cria estrutura KML
        kml = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
        document = ET.SubElement(kml, "Document")
        
        # Adiciona nome e descrição
        ET.SubElement(document, "name").text = f"Equipamentos - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        ET.SubElement(document, "description").text = f"Gerado pelo Bot Integrador - {len(items)} equipamentos"
        
        # Adiciona estilos
        cls._add_styles(document)
        
        # Cria pastas por tipo
        folder_postes_mt = ET.SubElement(document, "Folder")
        ET.SubElement(folder_postes_mt, "name").text = "Postes MT"
        
        folder_postes_bt = ET.SubElement(document, "Folder")
        ET.SubElement(folder_postes_bt, "name").text = "Postes BT"
        
        folder_instalacoes = ET.SubElement(document, "Folder")
        ET.SubElement(folder_instalacoes, "name").text = "Instalações"
        
        # Adiciona placemarks
        for item in items:
            if item.coordenadas is None:
                logger.warning(f"Item {item.codigo} sem coordenadas, pulando...")
                continue
            
            if isinstance(item, PosteData):
                if item.tem_mt:
                    cls._add_poste_placemark(folder_postes_mt, item, "poste_mt")
                else:
                    cls._add_poste_placemark(folder_postes_bt, item, "poste_bt")
            elif isinstance(item, InstalacaoData):
                cls._add_instalacao_placemark(folder_instalacoes, item)
        
        # Salva arquivo
        filepath = output_path / filename
        
        # Formata XML bonito
        xml_str = ET.tostring(kml, encoding='unicode')
        xml_pretty = minidom.parseString(xml_str).toprettyxml(indent="  ")
        
        # Remove linha de declaração duplicada
        lines = xml_pretty.split('\n')
        xml_pretty = '\n'.join(lines[1:])
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(xml_pretty)
        
        logger.info(f"KML gerado: {filepath} ({len(items)} equipamentos)")
        return filepath

    @classmethod
    def _add_styles(cls, document: ET.Element) -> None:
        """Adiciona estilos ao documento KML."""
        for style_id, style_config in cls.STYLES.items():
            style = ET.SubElement(document, "Style", id=style_id)
            icon_style = ET.SubElement(style, "IconStyle")
            ET.SubElement(icon_style, "scale").text = str(style_config["scale"])
            icon = ET.SubElement(icon_style, "Icon")
            ET.SubElement(icon, "href").text = style_config["icon"]

    @classmethod
    def _add_poste_placemark(
        cls,
        folder: ET.Element,
        poste: PosteData,
        style: str,
    ) -> None:
        """Adiciona placemark de poste."""
        placemark = ET.SubElement(folder, "Placemark")
        ET.SubElement(placemark, "name").text = f"Poste {poste.codigo}"
        ET.SubElement(placemark, "styleUrl").text = f"#{style}"
        
        # Descrição HTML
        desc_parts = [f"<b>Poste:</b> {poste.codigo}<br/>"]
        
        if poste.alimentador:
            desc_parts.append(f"<b>Alimentador:</b> {poste.alimentador}<br/>")
        
        if poste.estruturas_mt:
            desc_parts.append(f"<b>Estruturas MT:</b> {', '.join(poste.estruturas_mt)}<br/>")
        
        if poste.estruturas_bt:
            desc_parts.append(f"<b>Estruturas BT:</b> {', '.join(poste.estruturas_bt)}<br/>")
        
        if poste.cabos:
            desc_parts.append(f"<b>Cabos:</b><br/>")
            for cabo in poste.cabos:
                desc_parts.append(f"  • {cabo}<br/>")
        
        if poste.coordenadas:
            desc_parts.append(f"<br/><b>Coordenadas:</b> {poste.coordenadas.dms}<br/>")
            desc_parts.append(f"<a href='{poste.coordenadas.google_maps_url}'>Abrir no Google Maps</a>")
        
        ET.SubElement(placemark, "description").text = "".join(desc_parts)
        
        # Coordenadas (KML usa lon,lat,alt)
        point = ET.SubElement(placemark, "Point")
        ET.SubElement(point, "coordinates").text = (
            f"{poste.coordenadas.longitude},{poste.coordenadas.latitude},0"
        )

    @classmethod
    def _add_instalacao_placemark(
        cls,
        folder: ET.Element,
        instalacao: InstalacaoData,
    ) -> None:
        """Adiciona placemark de instalação."""
        placemark = ET.SubElement(folder, "Placemark")
        ET.SubElement(placemark, "name").text = f"Instalação {instalacao.codigo}"
        ET.SubElement(placemark, "styleUrl").text = "#instalacao"
        
        # Descrição HTML
        desc_parts = [f"<b>Instalação:</b> {instalacao.codigo}<br/>"]
        
        if instalacao.alimentador:
            desc_parts.append(f"<b>Alimentador:</b> {instalacao.alimentador}<br/>")
        
        if instalacao.perimetro:
            desc_parts.append(f"<b>Perímetro:</b> {instalacao.perimetro}<br/>")
        
        if instalacao.potencia:
            desc_parts.append(f"<b>Potência:</b> {instalacao.potencia}<br/>")
        
        if instalacao.fase:
            desc_parts.append(f"<b>Fase:</b> {instalacao.fase}<br/>")
        
        if instalacao.clientes:
            desc_parts.append(f"<b>Clientes:</b> {instalacao.clientes}<br/>")
        
        if instalacao.situacao:
            desc_parts.append(f"<b>Situação:</b> {instalacao.situacao}<br/>")
        
        if instalacao.poste:
            desc_parts.append(f"<b>Poste:</b> {instalacao.poste}<br/>")
        
        if instalacao.chaves_montante:
            desc_parts.append(f"<br/><b>Chaves a Montante:</b> {len(instalacao.chaves_montante)}<br/>")
        
        if instalacao.coordenadas:
            desc_parts.append(f"<br/><b>Coordenadas:</b> {instalacao.coordenadas.dms}<br/>")
            desc_parts.append(f"<a href='{instalacao.coordenadas.google_maps_url}'>Abrir no Google Maps</a>")
        
        ET.SubElement(placemark, "description").text = "".join(desc_parts)
        
        # Coordenadas
        point = ET.SubElement(placemark, "Point")
        ET.SubElement(point, "coordinates").text = (
            f"{instalacao.coordenadas.longitude},{instalacao.coordenadas.latitude},0"
        )

    @classmethod
    def generate_single(
        cls,
        item: Union[PosteData, InstalacaoData],
        output_dir: str = "./output",
    ) -> Path:
        """Gera KML para um único equipamento."""
        filename = f"{item.tipo.value}_{item.codigo}.kml"
        return cls.generate([item], filename=filename, output_dir=output_dir)
