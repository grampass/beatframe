"""Comprobaciones de retención sobre el video ya renderizado (2026-11-14). Baratas: 4 fotogramas por video.

- BUCLE: en Shorts y Reels el video vuelve a empezar solo. Si el último fotograma no se parece al primero, el salto se
  nota. Avisa por encima de `UMBRAL_BUCLE` (diferencia media de grises, 0–255, en la zona de la escena: sin título,
  barra ni subtítulos). Calibrado con 12 finales: los que empalman dan ~2,5; los que acaban en otro plano, 8–42.
  Un guion con `"bucle": false` no lo pide.
- ARRANQUE: si nada se mueve en el primer segundo, se pierde al espectador. Avisa por debajo de `UMBRAL_ARRANQUE`
  (todos los finales hechos superan 3,5).
- VACIO: si el primer fotograma casi no tiene contenido (fondo liso), avisa (mínimo medido en finales: 0,13).
Son avisos para la vista previa: se corrigen antes del final, sin volver a renderizar para descubrirlos.
"""
import io
import subprocess

import numpy as np
from PIL import Image

UMBRAL_BUCLE, UMBRAL_ARRANQUE, UMBRAL_VACIO = 6.0, 2.0, 0.05
ZONA = (0.12, 0.62)          # fracción de la altura: debajo del título y la barra, encima de los subtítulos


def duracion_imagen(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration",
                        "-of", "csv=p=0", str(video)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def fotograma(video, t):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(video), "-frames:v", "1",
                        "-vf", "scale=270:480", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, check=True)
    return np.asarray(Image.open(io.BytesIO(r.stdout)).convert("L"), float)


def zona(a):
    h = a.shape[0]
    return a[int(h * ZONA[0]):int(h * ZONA[1])]


def diferencia(a, b):
    return float(np.abs(zona(a) - zona(b)).mean())


def contenido(a):
    z = zona(a)
    return float((np.abs(z - np.median(z)) > 12).mean())


def medir(video):
    d = duracion_imagen(video)
    f0, f05, f1, fin = (fotograma(video, t) for t in (0.02, 0.5, 1.0, d - 0.15))
    return dict(bucle=diferencia(f0, fin), arranque=max(diferencia(f0, f05), diferencia(f0, f1)), contenido=contenido(f0))


def avisos(medidas, bucle=True):
    """[(código, mensaje)] a partir de medir()."""
    out = []
    if bucle and medidas["bucle"] > UMBRAL_BUCLE:
        out.append(("BUCLE", f"El último fotograma no empalma con el primero (diferencia {medidas['bucle']:.1f}; "
                             f"los que empalman bien dan ~2,5). En Shorts el salto se nota: vuelve al plano y la postura "
                             f"del primer beat al final, o pon \"bucle\": false en el guion si es a propósito"))
    if medidas["arranque"] < UMBRAL_ARRANQUE:
        out.append(("ARRANQUE", f"Nada se mueve en el primer segundo (cambio {medidas['arranque']:.1f}): anima algo "
                                f"desde el primer fotograma del gancho"))
    if medidas["contenido"] < UMBRAL_VACIO:
        out.append(("VACIO", f"El primer fotograma está casi vacío ({medidas['contenido']:.0%} con contenido): el gancho "
                             f"debe verse desde el inicio"))
    return out
