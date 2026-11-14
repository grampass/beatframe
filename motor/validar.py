"""Valida el contrato técnico y delega la política editorial a una extensión opcional."""
import json
import sys
from pathlib import Path

from configuracion import cargar_extension
from contrato import errores_palabras, estructura


class AvisoEditorial(str):
    def __new__(cls, texto, codigo, bloqueante):
        obj = super().__new__(cls, texto)
        obj.codigo, obj.bloqueante = codigo, bloqueante
        return obj


def validar(carpeta: Path, con_audio=False, estricto=False):
    """Sin extensión basta el contrato; una voz puede declararse en el propio beat."""
    extension = cargar_extension("validacion")
    if extension is not None:
        return extension.validar(carpeta, con_audio=con_audio, estricto=estricto)
    carpeta = Path(carpeta)
    try:
        g = json.loads((carpeta / "guion.json").read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        return [f"No se puede leer guion.json: {e}"], []
    errores = estructura(g)
    if errores or not con_audio:
        return errores, []
    try:
        tiempos = json.loads((carpeta / "audio/tiempos.json").read_text(encoding="utf-8"))
        if not isinstance(tiempos, dict):
            raise ValueError("se esperaba un objeto por beat")
    except (ValueError, OSError) as e:
        return [f"audio/tiempos.json inválido: {e}"], []
    for b in g["beats"]:
        bid = b["id"]
        if errores_palabras(tiempos.get(bid)):
            errores.append(f"{bid}: tiempos/palabras inválidos o vacíos")
        archivo = carpeta / "audio" / f"{bid}.mp3"
        if not archivo.is_file() or not archivo.stat().st_size:
            errores.append(f"{bid}: audio ausente o vacío")
    return errores, []


if __name__ == "__main__":
    for salida in (sys.stdout, sys.stderr):
        salida.reconfigure(encoding="utf-8", errors="replace")
    errores, avisos = validar(Path(sys.argv[1]), con_audio="--audio" in sys.argv)
    for x in errores:
        print("ERROR ", x)
    for x in avisos:
        print("AVISO ", x)
    print(f"{len(errores)} errores, {len(avisos)} avisos")
    sys.exit(1 if errores else 0)
