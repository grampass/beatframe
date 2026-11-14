"""Personaje de demostración: un pequeño robot de pantalla, dibujado solo con primitivas (sin imágenes ni fuentes).

Cara-pantalla con ojos y boca de luz (la boca sigue a la voz, los ojos parpadean y miran), cejas para las expresiones,
antena cuya luz es el indicador `carga` (0–1), un brazo articulado con mano redonda y una base que flota sobre su
sombra. Misma interfaz que cualquier personaje: poses, `anim()`, `alcanzar()`, `senalar()`, `ir_a()`.
"""
import numpy as np
from manim import Arc, Circle, Ellipse, Line, RoundedRectangle, VGroup, VMobject

from personajes.base import Personaje

CARCASA, TINTA, PANTALLA, BASE = "#EEF1F4", "#22303D", "#17232E", "#B8C4CF"
LUZ, ACENTO, APAGADO, MEJILLA = "#7FE6D8", "#FFC857", "#5B6773", "#FF8F7A"
HOMBRO = np.array([0.74, 1.02])


class Demo(Personaje):
    """Robot de demostración. `gesto` = (mirada x, mirada y, cejas): mirada en −1…1 y cejas −1 (preocupado) … 1 (alegre)."""
    CAMPOS = ("mano", "ctrl", "gesto")
    POSES = {
        "reposo": ((1.02, 0.52), (1.0, 0.8), (0, 0, 0)),
        "senala": ((1.62, 2.75), (1.3, 1.8), (0.4, 0.5, 0.4)),
        "explica": ((1.75, 1.55), (1.32, 1.2), (0.2, 0.1, 0.5)),
        "mira_abajo": ((1.45, 0.2), (1.18, 0.62), (0.3, -0.8, 0)),
        "jala": ((1.3, 0.1), (1.48, 0.7), (-0.2, -0.3, -0.5)),
    }
    EXTRAS = dict(parpado=1.0, carga=0.0)
    EXPRESIONES = {
        "alegre": dict(gesto=(0, 0.3, 1.0), reposo="c"),
        "sorpresa": dict(gesto=(0, 0.4, 0.8), reposo="o"),
        "duda": dict(gesto=(0.6, 0.4, -0.6), reposo="n"),
        "concentrada": dict(gesto=(0.3, -0.3, -0.3), reposo="n"),
        "fastidio": dict(gesto=(-0.3, 0, -1.0), reposo="f"),
    }
    MEDIO_ANCHO, ALTO = .8, 2.2
    HABLA = "demo"

    def __init__(self, pos=(0, -2), escala=1.0, pose="reposo"):
        super().__init__(pos, escala, pose)
        self.flotar = False
        self.refrescar()

    def _local(self, x, y):
        return np.array([x * self.e, y * self.e, 0.0])

    # ---------- dibujo (siempre las mismas piezas, en el mismo orden) ----------
    def _boca(self, y):
        forma = self.boca
        if forma == "a":
            m = Ellipse(width=0.26, height=0.17)
        elif forma == "m":
            m = Ellipse(width=0.24, height=0.08)
        elif forma == "o":
            m = Ellipse(width=0.13, height=0.14)
        elif forma == "f":                       # fastidio: media luna hacia abajo
            m = Arc(radius=0.13, start_angle=0, angle=np.pi)
        elif forma == "n":                       # neutra: una raya
            m = Line([-0.11, 0, 0], [0.11, 0, 0])
        else:                                    # "c": sonrisa (media luna hacia arriba)
            m = Arc(radius=0.13, start_angle=np.pi, angle=np.pi)
        return m.move_to([0, y, 0]).set_style(fill_color=LUZ, fill_opacity=0.95, stroke_color=LUZ, stroke_width=4)

    def _dibujar(self):
        mx, my, ceja = (float(v) for v in np.array(self.gesto, float).reshape(-1)[:3])
        dx, dy = 0.07 * np.clip(mx, -1, 1), 0.05 * np.clip(my, -1, 1)
        abierto = max(0.04, 0.27 * float(self.parpado) * (1.0 if self.ojos > 0.5 else 0.12))
        carga = float(np.clip(self.carga, 0, 1))

        sombra = Ellipse(width=1.25, height=0.16).move_to([0, 0.04, 0]).set_style(
            fill_color="#000000", fill_opacity=0.28, stroke_width=0)
        base = RoundedRectangle(width=0.9, height=0.3, corner_radius=0.15).move_to([0, 0.38, 0]).set_style(
            fill_color=BASE, fill_opacity=1, stroke_color=TINTA, stroke_width=4)
        chorro = Ellipse(width=0.62, height=0.12).move_to([0, 0.2, 0]).set_style(        # flota: luz bajo la base
            fill_color=LUZ, fill_opacity=0.5, stroke_width=0)
        cuello = RoundedRectangle(width=0.3, height=0.2, corner_radius=0.06).move_to([0, 0.56, 0]).set_style(
            fill_color=APAGADO, fill_opacity=1, stroke_color=TINTA, stroke_width=3)

        # brazo izquierdo en reposo (fijo) y orejas-tornillo, detrás de la carcasa
        brazo_izq = VGroup(Line([-0.72, 1.02, 0], [-0.9, 0.62, 0], stroke_color=TINTA, stroke_width=17),
                           Line([-0.72, 1.02, 0], [-0.9, 0.62, 0], stroke_color=CARCASA, stroke_width=11))
        mano_izq = Circle(0.13).move_to([-0.92, 0.56, 0]).set_style(fill_color=ACENTO, fill_opacity=1,
                                                                    stroke_color=TINTA, stroke_width=3)
        orejas = VGroup(*[Circle(0.1).move_to([x, 1.42, 0]).set_style(fill_color=APAGADO, fill_opacity=1,
                                                                        stroke_color=TINTA, stroke_width=3)
                          for x in (-0.79, 0.79)])

        # antena: su luz es el indicador de carga. refrescar() solo copia PUNTOS (no colores): la carga se dibuja con
        # tamaños (la luz crece dentro de la bombilla apagada y el halo se abre), nunca cambiando el color de una pieza.
        antena = Line([0, 2.08, 0], [0.1, 2.42, 0], stroke_color=TINTA, stroke_width=5)
        bombilla = Circle(0.1).move_to([0.1, 2.48, 0]).set_style(fill_color=APAGADO, fill_opacity=1,
                                                                 stroke_color=TINTA, stroke_width=3)
        luz = Circle(max(0.004, 0.085 * carga)).move_to([0.1, 2.48, 0]).set_style(fill_color=ACENTO, fill_opacity=1,
                                                                                stroke_width=0)
        halo = Circle(0.1 + 0.13 * carga).move_to([0.1, 2.48, 0]).set_style(fill_color=ACENTO, fill_opacity=0.25,
                                                                           stroke_width=0)

        carcasa = RoundedRectangle(width=1.56, height=1.5, corner_radius=0.5).move_to([0, 1.36, 0]).set_style(
            fill_color=CARCASA, fill_opacity=1, stroke_color=TINTA, stroke_width=5)
        brillo = Arc(radius=0.55, start_angle=np.radians(110), angle=np.radians(45)).move_arc_center_to(
            [0.05, 1.42, 0]).set_style(stroke_color="#FFFFFF", stroke_width=6, stroke_opacity=0.9)
        pantalla = RoundedRectangle(width=1.14, height=0.82, corner_radius=0.3).move_to([0, 1.5, 0]).set_style(
            fill_color=PANTALLA, fill_opacity=1, stroke_color=TINTA, stroke_width=3)

        ojos = VGroup(*[RoundedRectangle(width=0.17, height=abierto, corner_radius=min(0.085, abierto / 2))
                        .move_to([x + dx, 1.6 + dy, 0]).set_style(fill_color=LUZ, fill_opacity=1, stroke_width=0)
                        for x in (-0.24, 0.24)])
        # cejas: ceja > 0 las sube rectas (alegre, sorpresa); ceja < 0 baja los extremos interiores (fastidio)
        inclinacion, alto = 0.065 * max(0.0, -ceja), 1.83 + dy + 0.05 * max(0.0, ceja)
        cejas = VGroup(*[Line([x - 0.1, alto - lado * inclinacion, 0], [x + 0.1, alto + lado * inclinacion, 0],
                              stroke_color=LUZ, stroke_width=4, stroke_opacity=0.85)
                         for x, lado in ((-0.24, -1), (0.24, 1))])
        mejillas = VGroup(*[Ellipse(width=0.14, height=0.06).move_to([x, 1.36, 0]).set_style(
            fill_color=MEJILLA, fill_opacity=0.55, stroke_width=0) for x in (-0.4, 0.4)])
        boca = self._boca(1.32 + dy * 0.5)

        # indicador del pecho (también sigue a `carga`)
        riel = RoundedRectangle(width=0.8, height=0.12, corner_radius=0.06).move_to([0, 0.86, 0]).set_style(
            fill_color=PANTALLA, fill_opacity=1, stroke_width=0)
        lleno = Line([-0.36, 0.86, 0], [-0.36 + 0.72 * max(carga, 0.01), 0.86, 0], stroke_color=ACENTO, stroke_width=7)

        # brazo derecho articulado: tubo (contorno + relleno) y mano redonda; es la extremidad que señala
        hombro, codo, mano = (np.array([*HOMBRO, 0]), np.array([*self.ctrl, 0]), np.array([*self.mano, 0]))
        tubo = VGroup(*[VMobject().set_points_as_corners([hombro, codo, mano]).set_style(stroke_color=c, stroke_width=w)
                        for c, w in ((TINTA, 17), (CARCASA, 11))])
        tubo.extremidad = True
        punta = Circle(0.16).move_to(mano).set_style(fill_color=ACENTO, fill_opacity=1, stroke_color=TINTA, stroke_width=3)
        punta.extremidad = True
        hombro_pieza = Circle(0.1).move_to(hombro).set_style(fill_color=APAGADO, fill_opacity=1,
                                                             stroke_color=TINTA, stroke_width=3)

        return VGroup(sombra, chorro, base, cuello, brazo_izq, mano_izq, orejas, antena, halo, bombilla, luz, carcasa,
                      brillo, pantalla, mejillas, ojos, cejas, boca, riel, lleno, tubo, hombro_pieza, punta
                      ).scale(self.e, about_point=[0, 0, 0])

    def alcanzar(self, x, y):
        origen = self.punto(0, 0)
        matriz = np.column_stack(((self.punto(1, 0) - origen)[:2], (self.punto(0, 1) - origen)[:2]))
        mano = np.linalg.solve(matriz, np.array([x, y]) - origen[:2])
        # codo a medio camino, un poco hacia fuera y abajo: el brazo se ve doblado, no como una vara
        return dict(mano=mano, ctrl=(mano + HOMBRO) / 2 + np.array([0.1, -0.08]))
