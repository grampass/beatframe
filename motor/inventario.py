"""Entrada compatible de la herramienta de inventario configurada externamente."""
import sys
from configuracion import cargar_extension

_implementacion = cargar_extension("inventario")
if _implementacion is None:
    raise RuntimeError("No hay una herramienta de inventario configurada")
if __name__ == "__main__":
    sys.exit(_implementacion.main())
else:
    sys.modules[__name__] = _implementacion
