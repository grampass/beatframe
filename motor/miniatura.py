"""Miniaturas desde el propio video (2026-11-14).

Saca un fotograma del video en la PAUSA después de un beat (sin subtítulo encima) y arma dos imágenes:
  miniatura-16x9.png   1280×720: el título grande a la izquierda y la escena a la derecha (YouTube y Facebook)
  miniatura-9x16.png   1080×1920: el fotograma con el título grande arriba (portada de Reels y Shorts)
Colores y fuente salen de la configuración visual (FONDO, TIZA, AMBAR, FUENTE): el estilo es el de los videos.

Uso:  python motor/miniatura.py <carpeta> [--beat b7] [--titulo "TEXTO"] [--video final.mp4]
Por defecto: el beat central, el título del guion y final.mp4 (o vista-previa.mp4 si no hay final).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

MOTOR = Path(__file__).resolve().parent
sys.path.insert(0, str(MOTOR))
from configuracion import CONFIG  # noqa: E402

_VIS = CONFIG.get("visual", {})
FONDO, TIZA, AMBAR = _VIS.get("FONDO", "#000000"), _VIS.get("TIZA", "#FFFFFF"), _VIS.get("AMBAR", "#FFBF00")
_fuentes = {}


def buscar_fuente(familia):
    """Archivo de la fuente cuyo nombre empieza por `familia` (negrita si la hay); None si no se encuentra."""
    if familia in _fuentes:
        return _fuentes[familia]
    dirs = [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Fonts",
            Path("/usr/share/fonts"), Path("/Library/Fonts"), Path.home() / ".fonts"]
    candidatos = []
    for d in dirs:
        if d.is_dir():
            for p in d.rglob("*"):
                if p.suffix.lower() in (".ttf", ".otf"):
                    try:
                        nombre, estilo = ImageFont.truetype(str(p), 12).getname()
                    except OSError:
                        continue
                    if nombre.casefold().startswith(familia.casefold()):
                        candidatos.append((0 if "bold" in estilo.casefold() else 1, str(p)))
    _fuentes[familia] = sorted(candidatos)[0][1] if candidatos else None
    return _fuentes[familia]


def fuente(tam):
    ruta = buscar_fuente(_VIS.get("FUENTE", "Arial")) or buscar_fuente("Arial") or buscar_fuente("DejaVu Sans")
    return ImageFont.truetype(ruta, tam) if ruta else ImageFont.load_default(tam)


def instante(carpeta, beat=None):
    """Segundo del video en la pausa tras `beat` (por defecto, el beat central): ahí no hay subtítulo."""
    from nucleo import Guion
    g = Guion(Path(carpeta))
    b = g[beat] if beat else g.beats[len(g.beats) // 2]
    return b["fin"] + 0.14


def fotograma(video, t):
    with tempfile.TemporaryDirectory() as d:
        salida = Path(d) / "f.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", str(salida)],
                       check=True)
        return Image.open(salida).convert("RGB").copy()


def partir(texto, f, ancho, dibujo):
    """Líneas que caben en `ancho` con la fuente `f`."""
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = (actual + " " + palabra).strip()
        if actual and dibujo.textlength(prueba, font=f) > ancho:
            lineas.append(actual)
            actual = palabra
        else:
            actual = prueba
    return lineas + ([actual] if actual else [])


def titulo_en(img, texto, caja, tam_max, max_lineas=4, borde=0):
    """Escribe `texto` lo más grande posible dentro de caja (x0, y0, x1, y1). Última palabra en AMBAR."""
    dib = ImageDraw.Draw(img)
    x0, y0, x1, y1 = caja
    for tam in range(tam_max, 20, -4):
        f = fuente(tam)
        lineas = partir(texto, f, x1 - x0, dib)
        alto = len(lineas) * tam * 1.12
        cabe = max(dib.textlength(l, font=f) for l in lineas) <= x1 - x0      # una palabra larga sola tampoco se sale
        if len(lineas) <= max_lineas and alto <= y1 - y0 and cabe:
            break
    y = y0 + ((y1 - y0) - alto) / 2
    for i, linea in enumerate(lineas):
        palabras = linea.split()
        x = x0
        for j, w in enumerate(palabras):
            ultima = i == len(lineas) - 1 and j == len(palabras) - 1
            dib.text((x, y), w, font=f, fill=AMBAR if ultima else TIZA, stroke_width=borde, stroke_fill=FONDO)
            x += dib.textlength(w + " ", font=f)
        y += tam * 1.12
    return tam


def miniaturas(carpeta, beat=None, titulo=None, video=None):
    carpeta = Path(carpeta)
    g = json.loads((carpeta / "guion.json").read_text(encoding="utf-8"))
    titulo = (titulo or g.get("titulo_completo") or g.get("titulo", "")).upper()
    video = Path(video) if video else next((carpeta / n for n in ("final.mp4", "vista-previa.mp4") if (carpeta / n).is_file()), None)
    if video is None:
        raise FileNotFoundError("No hay final.mp4 ni vista-previa.mp4: produce el video antes")
    cuadro = fotograma(video, instante(carpeta, beat)).resize((1080, 1920))
    escena = cuadro.crop((0, 230, 1080, 1310))                  # entre el título y los subtítulos

    ancha = Image.new("RGB", (1280, 720), FONDO)
    fondo = escena.resize((1280, 1280)).crop((0, 280, 1280, 1000)).filter(ImageFilter.GaussianBlur(28))
    ancha.paste(Image.blend(fondo, Image.new("RGB", fondo.size, FONDO), 0.72))
    ancha.paste(escena.resize((660, 660)), (590, 30))
    ImageDraw.Draw(ancha).rounded_rectangle((44, 70, 54, 650), radius=5, fill=AMBAR)
    titulo_en(ancha, titulo, (80, 60, 600, 660), 110, borde=4)

    alta = cuadro.copy()
    banda = Image.new("RGB", (1080, 640), FONDO)
    alta.paste(banda.crop((0, 0, 1080, 600)), (0, 0))                  # tapa el título pequeño del video
    for k in range(40):                                                    # borde suave hacia la escena
        y = 600 + k
        fila = alta.crop((0, y, 1080, y + 1))
        alta.paste(Image.blend(fila, banda.crop((0, 0, 1080, 1)), 1 - k / 40), (0, y))
    titulo_en(alta, titulo, (70, 70, 1010, 580), 150, borde=6)

    salidas = (carpeta / "miniatura-16x9.png", carpeta / "miniatura-9x16.png")
    ancha.save(salidas[0], optimize=True)
    alta.save(salidas[1], optimize=True)
    return salidas


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta", type=Path)
    ap.add_argument("--beat")
    ap.add_argument("--titulo")
    ap.add_argument("--video", type=Path)
    a = ap.parse_args()
    for s in miniaturas(a.carpeta, a.beat, a.titulo, a.video):
        print(s)
