"""Recetas de actuación con objetos reutilizables.

Acciones que se repiten entre episodios, para no reescribirlas en cada escena:
- `TazaVacia(base, escala)`: la Taza oficial vacía (interior oscuro, sin vapor), a la escala pedida.
- `NotaMesa(x, y, giro)`: nota pequeña boca abajo sobre la mesa (dorso liso, sin texto: no gasta presupuesto de textos).
- `NotaGrande(texto)` + `.girar()`: la nota de un inserto; se estrecha, cambia de cara y vuelve. Texto siempre dentro.
- `ManoInserto(punta)`: borde de una mano (puño y manga) para insertos de objeto/mano, sin torso.
- `empujar(personaje, objeto, destino, toque)`: la mano y el objeto se mueven juntos, sin soltarlo.
El personaje debe implementar `alcanzar(x, y)` para situar la mano en un punto de escena.

Uso con un actor que implemente ese método:
    taza2 = TazaVacia(P0, 0.8)
    actor.poner(**actor.alcanzar(*taza2.borde()))
    self.en("b1", "Te", *empujar(actor, taza2, P1), run_time=0.9)
    nota = NotaGrande("Pieza lista"); self.play(nota.girar())        # dentro de un inserto (grupo con .inserto = True)
"""
import numpy as np
from manim import (PI, Circle, Polygon, RoundedRectangle, UpdateFromAlphaFunc, VGroup, rate_functions)

from nucleo import FONDO, LILA, TIZA, nota, tiza
from piezas.basicas import Taza

PAPEL, PAPEL_DORSO, TINTA, INTERIOR = "#C9C3EE", LILA, FONDO, "#1B1F27"


class TazaVacia(Taza):
    """La Taza oficial sin café. `base` es el centro de su base (como Taza); `borde()` es el punto donde se apoya
    la mano. La posición se lleva en `self.base`, y empujar() la actualiza."""

    def __init__(self, base, escala=1.0):
        super().__init__(base, temp=0.0)
        self.cuerpo.set_fill(INTERIOR, 1)
        self.vapor.set_stroke(opacity=0)
        self.escala = escala
        self.base = (float(base[0]), float(base[1]))
        self.scale(escala, about_point=[base[0], base[1], 0])

    def set_temp(self, c):              # siempre vacía: ni color de café ni vapor
        self.temp = c
        return self

    def borde(self, base=None):
        x, y = self.base if base is None else base
        return (x - 0.05, y + 1.19 * self.escala)


class NotaMesa(VGroup):
    """Nota pequeña boca abajo. No tiene texto: se lee solo en su inserto (NotaGrande)."""

    def __init__(self, x, y, giro=0, ancho=0.62, alto=0.42):
        super().__init__()
        self.add(tiza(RoundedRectangle(corner_radius=0.04, width=ancho, height=alto, stroke_color=TIZA, stroke_width=3,
                                       fill_color=PAPEL_DORSO, fill_opacity=0.95), 21))
        self.rotate(np.radians(giro)).move_to([x, y, 0])


class NotaGrande(VGroup):
    """Nota de inserto con dorso y cara. Empieza boca abajo; cada `girar()` la voltea (dos giros = boca abajo otra vez)."""

    def __init__(self, texto, ancho=3.4, alto=2.3, giro=-4, tam=46):
        super().__init__()
        base = lambda c: tiza(RoundedRectangle(corner_radius=0.12, width=ancho, height=alto, stroke_color=TIZA,
                                               stroke_width=6, fill_color=c, fill_opacity=1), 23)
        self.dorso = base(PAPEL_DORSO)
        letra = nota(texto, color=TINTA, tam=tam)
        if letra.width > ancho * 0.8:
            letra.scale_to_fit_width(ancho * 0.8)          # el texto entero dentro del papel
        self.letra = letra
        self.cara = VGroup(base(PAPEL), letra)
        self.cara.set_opacity(0)
        self.add(self.dorso, self.cara).rotate(np.radians(giro))
        self.boca_arriba = False

    def girar(self, run_time=0.6):
        ref = self.copy()
        a_cara = not self.boca_arriba
        self.boca_arriba = a_cara

        def f(m, al):
            m.become(ref)
            if al >= 0.5:                                   # a mitad del giro cambia de cara
                (m.cara if a_cara else m.dorso).set_opacity(1)
                (m.dorso if a_cara else m.cara).set_opacity(0)
            m.stretch(max(0.02, abs(np.cos(PI * al))), 0)
        return UpdateFromAlphaFunc(self, f, run_time=run_time, rate_func=rate_functions.smooth)


class ManoInserto(VGroup):
    """Puño y manga entrando desde abajo a la derecha hasta `punta` (borde de mano, sin torso)."""

    def __init__(self, punta):
        super().__init__()
        from registro import crear_pieza
        self.add(crear_pieza("mano_inserto", punta))


def empujar(personaje, objeto, destino, **campos):
    """Animaciones para mover `objeto` (con `.base` y `.borde()`, p. ej. TazaVacia) hasta `destino` con la mano
    apoyada en su borde todo el recorrido. `campos` extra (gesto=…) van a la animación del personaje."""
    d = np.array([destino[0] - objeto.base[0], destino[1] - objeto.base[1], 0.0])
    objeto.base = (float(destino[0]), float(destino[1]))
    return objeto.animate.shift(d).build(), personaje.anim(**personaje.alcanzar(*objeto.borde()), **campos)
