"""Entrada compatible de la herramienta de archivo configurada externamente."""
import sys
from configuracion import cargar_extension

_implementacion = cargar_extension("papelera")
if _implementacion is None:
    raise RuntimeError("No hay una herramienta de archivo configurada")
if __name__ == "__main__":
    sys.exit(_implementacion.main())
else:
    sys.modules[__name__] = _implementacion
