"""Ejemplo sin red: tonos propios y marcas escritas, sin narración sintetizada."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = next(p for p in AQUI.parents if (p / "motor").is_dir())
os.environ["MOTOR_CONFIG"] = "-"
sys.path.insert(0, str(RAIZ / "motor"))
from contrato import argumentos_voz


def preparar():
    audio = AQUI / "audio"
    audio.mkdir(exist_ok=True)
    guion = json.loads((AQUI / "guion.json").read_text(encoding="utf-8"))
    tiempos, huellas = {}, {}
    for i, beat in enumerate(guion["beats"]):
        palabras = beat["texto"].split()
        tiempos[beat["id"]] = [dict(w=w, t=.45*k, d=.38) for k,w in enumerate(palabras)]
        duracion = .45 * len(palabras)
        destino = audio / f"{beat['id']}.mp3"
        if not destino.exists():
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                f"sine=frequency={440+i*110}:duration={duracion}", "-af", "volume=0.08",
                "-map_metadata", "-1", "-q:a", "9", str(destino)], check=True)
        huellas[beat["id"]] = hashlib.md5("|".join(argumentos_voz(beat)).encode()).hexdigest()
    for nombre, datos in (("tiempos.json", tiempos), ("huellas.json", huellas)):
        (audio / nombre).write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    preparar()
    env = dict(os.environ, PYTHONPATH=str(RAIZ / "motor"))
    sys.exit(subprocess.call([sys.executable, str(RAIZ / "motor/producir.py"), str(AQUI), *sys.argv[1:]], env=env))
