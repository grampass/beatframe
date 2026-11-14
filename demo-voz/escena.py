"""Narrated demo: every action is anchored to a spoken word with self.en(bid, word, ...)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("MOTOR_CONFIG", "-")
for padre in Path(__file__).resolve().parents:
    if (padre / "motor").is_dir():
        sys.path.insert(0, str(padre / "motor"))
        break
else:
    import beatframe  # noqa: F401  (installed with pip: puts the engine modules on the path)

import numpy as np
from estudio import (EscenaEstudio, Plano, Circle, Create, Dot, FadeIn, Line, RoundedRectangle, VGroup,
                     VMobject, AMBAR, TIZA, GRIS)
from personajes.demo import Demo

BASE = (-1.75, -1.5)           # robot feet, inside the «principal» zone
BOLA = np.array([1.5, -1.12, 0])


def fondo():
    """Dim dot grid and a floor line: depth without images."""
    puntos = VGroup(*[Dot([x, y, 0], radius=0.025, color=GRIS, fill_opacity=0.35)
                      for x in np.arange(-4.0, 3.3, 0.6) for y in np.arange(-1.2, 6.0, 0.6)])
    suelo = Line([-4.2, -1.5, 0], [3.1, -1.5, 0], stroke_color=GRIS, stroke_width=3, stroke_opacity=0.6)
    g = VGroup(puntos, suelo)
    for m in g.get_family():
        m.no_revisar = True
    return g


def bola():
    b = VGroup(Circle(0.38, fill_color=AMBAR, fill_opacity=1, stroke_color="#22303D", stroke_width=4),
               Line([-0.38, 0, 0], [0.38, 0, 0], stroke_color="#22303D", stroke_width=5))     # the stripe shows it rolling
    b.move_to(BOLA)
    b.importante = True
    return b


def lista():
    """Checklist card with a tick that draws itself."""
    tarjeta = RoundedRectangle(width=1.8, height=1.7, corner_radius=0.2, fill_color="#17232E", fill_opacity=1,
                               stroke_color=TIZA, stroke_width=3)
    renglones = VGroup(*[Line([-0.55, y, 0], [0.55, y, 0], stroke_color=GRIS, stroke_width=5) for y in (0.35, 0.0, -0.35)])
    tic = VMobject(stroke_color="#7FE6D8", stroke_width=12).set_points_as_corners([[-0.45, 0.05, 0], [-0.1, -0.35, 0], [0.55, 0.45, 0]])
    g = VGroup(tarjeta, renglones).move_to([2.17, 3.6, 0])
    tic.move_to(g.get_center())
    g.importante = True
    return g, tic


class DemoVoz(EscenaEstudio):
    carpeta = Path(__file__).resolve().parent

    def construct(self):
        self.plano = Plano("laboratorio")
        self.sub_y = self.plano.sub_y
        self.add(fondo())
        robot = Demo(pos=BASE, escala=2.3).conectar(self)
        pelota = bola()
        self.add(robot, pelota)

        # b1 · waves on «Hi», smiles
        self.en("b1", "hi", robot.anim(pose="explica", expresion="alegre"), run_time=0.45, antes=0.1)
        self.en("b1", "script", robot.anim(pose="reposo"), run_time=0.5)
        self.fin_beat("b1")

        # b2 · points up on «word»; one label
        self.en("b2", "word", robot.anim(pose="senala", expresion="sorpresa"),
                *self.rotulo_anim("1 WORD = 1 MOVE", hasta="b2", tam=34), run_time=0.5)
        self.fin_beat("b2")

        # b3 · reaches the ball, and on «push» the ball rolls away
        self.en("b3", "when", robot.anim(**robot.alcanzar(*(BOLA[:2] - [0.42, 0])), expresion="concentrada"), run_time=0.6)
        self.en("b3", "push", pelota.animate.shift([1.2, 0, 0]).rotate(-np.pi * 1.0),
                robot.anim(**robot.alcanzar(*(BOLA[:2] + [0.25, 0.05])), expresion="alegre"), run_time=0.9)
        self.en("b3", "away", robot.anim(pose="reposo"), run_time=0.5)
        self.fin_beat("b3")

        # b4 · on «charge» the antenna lights up and the chest meter fills
        self.en("b4", "charge", robot.anim(carga=1.0, expresion="sorpresa"), run_time=1.2)
        self.en("b4", "lights", robot.anim(expresion="alegre"), run_time=0.4)
        self.fin_beat("b4")

        # b5 · a checklist appears; its tick draws on «caught»
        tarjeta, tic = lista()
        self.en("b5", "overlaps", FadeIn(tarjeta), robot.anim(pose="explica", gesto=(0.8, 0.7, 0.2)), run_time=0.5)
        self.en("b5", "caught", Create(tic), robot.anim(expresion="alegre"), run_time=0.6)
        self.fin_beat("b5")

        # b6 · back to rest, happy
        self.en("b6", "write", robot.anim(pose="reposo", gesto=(0, 0.2, 1.0)), run_time=0.6)
        self.en("b6", "timing", robot.anim(pose="explica"), run_time=0.45)
        self.en("b6", "itself", robot.anim(pose="reposo"), run_time=0.45)
        self.fin_beat("b6")
