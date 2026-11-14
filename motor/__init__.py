"""beatframe: animaciones ancladas a palabras habladas.

Instalado con pip, este paquete añade su carpeta al sys.path para que los módulos se importen igual que en un clon
(`from estudio import *`). En el repositorio no hace falta: los scripts se ejecutan desde `motor/`.
"""
import sys as _sys
from pathlib import Path as _Path

_AQUI = str(_Path(__file__).resolve().parent)
if _AQUI not in _sys.path:
    _sys.path.insert(0, _AQUI)

__version__ = "0.2.0"
