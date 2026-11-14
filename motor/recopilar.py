"""Recopilación horizontal (16:9) de varios videos verticales terminados (2026-11-14).

Para YouTube largo: cada parte abre con una tarjeta de título de 2,5 s y luego el video vertical centrado sobre una
copia suya ampliada, desenfocada y oscurecida (sin bandas negras). Además escribe:
  capitulos.txt      marcas «0:00 Título» para pegar en la descripción (YouTube crea los capítulos solo)
  recopilacion.srt   los subtítulos de todas las partes, desplazados a su sitio
No toca los videos de origen ni vuelve a renderizar escenas: solo compone los final.mp4 existentes.

Uso:  python motor/recopilar.py <salida> <carpeta1> <carpeta2> ... [--titulo "TÍTULO GENERAL"]
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

MOTOR = Path(__file__).resolve().parent
sys.path.insert(0, str(MOTOR))
from miniatura import AMBAR, FONDO, TIZA, fuente, titulo_en  # noqa: E402

TARJETA, FPS, SR = 2.5, 30, 48000
ANCHO, ALTO = 1920, 1080
_ENC = ["-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2"]


def _ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *map(str, args)], check=True)


def duracion(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def marca(t):
    t = int(t)
    return f"{t // 3600}:{t // 60 % 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def tarjeta(texto, parte, ruta):
    img = Image.new("RGB", (ANCHO, ALTO), FONDO)
    d = ImageDraw.Draw(img)
    d.text((160, 250), f"PARTE {parte}", font=fuente(54), fill=AMBAR)
    d.rounded_rectangle((160, 330, 260, 340), radius=5, fill=AMBAR)
    titulo_en(img, texto.upper(), (160, 380, 1760, 860), 130, max_lineas=3, borde=4)
    img.save(ruta)


def capitulos(titulos, inicios):
    """Líneas para la descripción. YouTube pide la primera en 0:00, al menos 3 y cada una de 10 s o más."""
    return "\n".join(f"{marca(t)} {x}" for x, t in zip(titulos, inicios)) + "\n"


def srt_desplazado(partes):
    """[(carpeta, desplazamiento)] → un solo .srt con los subtítulos de cada parte en su sitio."""
    from nucleo import Guion
    from subtitulos import cues, srt
    todos = []
    for carpeta, desde in partes:
        todos += [(a + desde, b + desde, t) for a, b, t in cues(Guion(Path(carpeta)).beats)]
    return srt(todos)


def recopilar(salida, carpetas, titulo=None):
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    titulos, inicios, partes, t = [], [], [], 0.0
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        trozos = []
        for i, c in enumerate(map(Path, carpetas), 1):
            video = c / "final.mp4"
            if not video.is_file():
                raise FileNotFoundError(f"{c.name}: falta final.mp4")
            g = json.loads((c / "guion.json").read_text(encoding="utf-8"))
            nombre = g.get("titulo_completo") or g.get("titulo", c.name)
            tarjeta(nombre, i, d / f"t{i}.png")
            _ff("-loop", 1, "-t", TARJETA, "-i", d / f"t{i}.png", "-f", "lavfi", "-t", TARJETA,
                "-i", f"anullsrc=r={SR}:cl=stereo", "-shortest", *_ENC, d / f"a{i}.mp4")
            _ff("-i", video, "-filter_complex",
                f"[0:v]scale={ANCHO}:{ALTO}:force_original_aspect_ratio=increase,crop={ANCHO}:{ALTO},"
                f"boxblur=40:4,eq=brightness=-0.28[f];[0:v]scale=-2:{ALTO}[v];[f][v]overlay=(W-w)/2:0,fps={FPS}[o]",
                "-map", "[o]", "-map", "0:a", *_ENC, d / f"b{i}.mp4")
            titulos.append(nombre)
            inicios.append(t)
            t += duracion(d / f"a{i}.mp4")
            partes.append((c, t))
            t += duracion(d / f"b{i}.mp4")
            trozos += [d / f"a{i}.mp4", d / f"b{i}.mp4"]
        lista = d / "lista.txt"
        lista.write_text("".join(f"file '{p.as_posix()}'\n" for p in trozos), encoding="utf-8")
        _ff("-f", "concat", "-safe", 0, "-i", lista, "-c", "copy", "-movflags", "+faststart", salida / "recopilacion.mp4")
    (salida / "capitulos.txt").write_text(capitulos(titulos, inicios), encoding="utf-8")
    (salida / "recopilacion.srt").write_text(srt_desplazado(partes), encoding="utf-8")
    if titulo:
        (salida / "titulo.txt").write_text(titulo + "\n", encoding="utf-8")
    return salida / "recopilacion.mp4", t


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("salida", type=Path)
    ap.add_argument("carpetas", nargs="+", type=Path)
    ap.add_argument("--titulo")
    a = ap.parse_args()
    video, total = recopilar(a.salida, a.carpetas, a.titulo)
    print(f"{video} · {total:.1f} s · capítulos y subtítulos junto al video")
    if len(a.carpetas) < 3:
        print("[AVISO] YouTube solo crea capítulos con 3 partes o más: con menos, capitulos.txt es orientativo")
