"""Subtítulos .srt desde los tiempos de la voz (2026-11-14).

Mismos tiempos que los subtítulos quemados en el video: cada subtítulo aparece en su primera palabra y se va 0,18 s
después de la última. Pero en frases (hasta 42 letras, cortando en cada oración), con el texto escrito como en el
guion: es lo que leen las plataformas para la búsqueda, la accesibilidad y la traducción automática.

Uso:  python motor/subtitulos.py <carpeta>      escribe <carpeta>/subtitulos.srt
producir.py lo escribe solo junto a vista-previa.mp4 / final.mp4.
"""
import re
import sys
from pathlib import Path

MOTOR = Path(__file__).resolve().parent
sys.path.insert(0, str(MOTOR))


def _marca(t):
    ms = max(0, round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def _escritas(b):
    """Las palabras como están en el guion (tildes, mayúsculas, signos) si coinciden una a una con las de la voz."""
    tokens = str(b.get("texto", "")).split()
    return tokens if len(tokens) == len(b["palabras"]) else [p["w"] for p in b["palabras"]]


def cues(beats, max_letras=42, pausa=0.5, cola=0.18):
    """[(inicio, fin, texto)] en el reloj del video. Frases legibles para subtítulos de plataforma: hasta
    `max_letras` por subtítulo, cortando al final de cada oración o en una pausa larga de la voz. (En el video se
    queman bloques de 3 palabras, `nucleo.bloques_subtitulos`; aquí conviene leer frases.) `beats`: los de
    nucleo.Guion, con las palabras en tiempo absoluto."""
    out = []
    for b in beats:
        actual = []
        for p, w in zip(b["palabras"], _escritas(b)):
            if actual:
                largo = sum(len(x[1]) + 1 for x in actual) + len(w)
                if largo > max_letras or p["t"] - (actual[-1][0]["t"] + actual[-1][0]["d"]) > pausa:
                    out.append(actual)
                    actual = []
            actual.append((p, w))
            if w[-1:] in ".?!…":
                out.append(actual)
                actual = []
        if actual:
            out.append(actual)
    res = [[bl[0][0]["t"], bl[-1][0]["t"] + bl[-1][0]["d"] + cola, " ".join(w for _, w in bl)] for bl in out]
    for a, b in zip(res, res[1:]):          # nunca dos a la vez: el anterior se va cuando entra el siguiente
        a[1] = min(a[1], b[0])
    return [tuple(c) for c in res if c[1] > c[0]]


def srt(cues_):
    return "".join(f"{i}\n{_marca(a)} --> {_marca(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(cues_, 1))


def escribir(carpeta, destino=None):
    from nucleo import Guion
    carpeta = Path(carpeta)
    destino = Path(destino) if destino else carpeta / "subtitulos.srt"
    destino.write_text(srt(cues(Guion(carpeta).beats)), encoding="utf-8")
    return destino


if __name__ == "__main__":
    print(escribir(Path(sys.argv[1])))
