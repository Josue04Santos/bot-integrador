"""Permite que pytest encontre o pacote 'src' a partir da raiz do projeto."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
