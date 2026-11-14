"""Alias de módulos opcionales declarados por una extensión local.

Ambas rutas devuelven el mismo módulo; no se ejecuta una segunda copia del
archivo ni se cambia su nombre canónico. Sin configuración no instala nada.
"""
import importlib
import importlib.abc
import importlib.util
import sys

from configuracion import CONFIG, RAIZ


class _Alias(importlib.abc.Loader):
    def __init__(self, destino):
        self.destino = destino

    def create_module(self, spec):
        modulo = importlib.import_module(self.destino)
        self.original = modulo.__spec__
        return modulo

    def exec_module(self, modulo):
        # importlib asigna el spec del alias al módulo existente al cargarlo.
        modulo.__spec__ = self.original


class _Buscador(importlib.abc.MetaPathFinder):
    def __init__(self, alias):
        self.alias = alias

    def find_spec(self, fullname, path=None, target=None):
        destino = self.alias.get(fullname)
        if destino is not None:
            return importlib.util.spec_from_loader(fullname, _Alias(destino))
        return None


_BUSCADOR = None


def instalar_compatibilidad():
    """Habilita imports antiguos sin dependencias concretas en los paquetes base."""
    global _BUSCADOR
    if _BUSCADOR is not None:
        return
    alias = CONFIG.get("modulos_compatibles", {})
    if not isinstance(alias, dict):
        raise ValueError("modulos_compatibles debe ser un objeto")
    for origen, destino in alias.items():
        if not all(isinstance(n, str) and "." in n and all(p.isidentifier() for p in n.split("."))
                   for n in (origen, destino)):
            raise ValueError("Los alias deben ser nombres de submódulos válidos")
        if destino in alias:
            raise ValueError("No se permiten cadenas ni ciclos entre alias de módulos")
    if alias:
        if str(RAIZ) not in sys.path:
            sys.path.insert(0, str(RAIZ))
        _BUSCADOR = _Buscador(dict(alias))
        sys.meta_path.insert(0, _BUSCADOR)
