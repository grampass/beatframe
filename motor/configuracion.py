"""Configuración y extensiones locales opcionales; sin dependencias gráficas.

Sin manifiesto se usan los valores genéricos. MOTOR_CONFIG permite seleccionar
otro manifiesto; el valor '-' desactiva toda configuración externa.
"""
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def leer_objeto(ruta):
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if not isinstance(datos, dict):
        raise ValueError(f"Configuración inválida en {ruta}: se esperaba un objeto")
    return datos


def cargar_configuracion(manifiesto=None):
    elegido = os.environ.get("MOTOR_CONFIG") if manifiesto is None else str(manifiesto)
    if elegido == "-":
        return {}, ()
    p = Path(elegido) if elegido else RAIZ / "motor.config.json"
    p = p if p.is_absolute() else RAIZ / p
    if not p.exists():
        if elegido:
            raise FileNotFoundError(f"No existe el manifiesto configurado: {p}")
        return {}, ()
    descriptor = leer_objeto(p)
    directorio = Path(descriptor["configuracion"])
    directorio = directorio if directorio.is_absolute() else p.parent / directorio
    principal = directorio / "config.json"
    datos = leer_objeto(principal)
    archivos = [p.resolve(), principal.resolve()]
    for nombre in datos.pop("archivos", []):
        archivo = directorio / nombre
        extra = leer_objeto(archivo)
        if repetidos := datos.keys() & extra.keys():
            raise ValueError(f"Claves de configuración repetidas en {archivo}: {sorted(repetidos)}")
        datos.update(extra)
        archivos.append(archivo.resolve())
    return datos, tuple(archivos)


CONFIG, ARCHIVOS_CONFIG = cargar_configuracion()
_EXTENSIONES = {}


def ruta(nombre, defecto):
    valor = CONFIG.get("rutas", {}).get(nombre)
    if valor is None:
        return Path(defecto)
    if not isinstance(valor, str):
        raise ValueError(f"La ruta {nombre!r} debe ser texto")
    p = Path(valor)
    return p if p.is_absolute() else RAIZ / p


def cargar_extension(nombre):
    """Carga una extensión configurada explícitamente; sus fallos no se ocultan."""
    archivo = CONFIG.get("extensiones", {}).get(nombre)
    if archivo is None:
        return None
    p = Path(archivo)
    p = (p if p.is_absolute() else RAIZ / p).resolve()
    if p in _EXTENSIONES:
        return _EXTENSIONES[p]
    identificador = "_motor_extension_" + hashlib.sha256(str(p).encode()).hexdigest()[:20]
    spec = importlib.util.spec_from_file_location(identificador, p)
    if spec is None or spec.loader is None:
        raise ValueError(f"Extensión no cargable: {p}")
    if str(RAIZ) not in sys.path:
        sys.path.insert(0, str(RAIZ))
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[identificador] = modulo
    try:
        spec.loader.exec_module(modulo)
    except BaseException:
        sys.modules.pop(identificador, None)
        raise
    _EXTENSIONES[p] = modulo
    return modulo


def archivos_configuracion():
    """Fuentes externas que invalidan la caché, incluidas reglas y extensiones."""
    archivos = set(ARCHIVOS_CONFIG)
    for principal in ARCHIVOS_CONFIG[1:2]:
        archivos.update(p for p in principal.parent.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    for valor in CONFIG.get("extensiones", {}).values():
        p = Path(valor)
        p = p if p.is_absolute() else RAIZ / p
        archivos.update(f for f in p.parent.rglob("*.py")
                        if "__pycache__" not in f.parts and "_archivo" not in f.parts)
    return archivos
