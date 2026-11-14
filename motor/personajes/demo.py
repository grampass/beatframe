"""Manipulador geométrico de demostración, dibujado solo con primitivas."""
import numpy as np
from manim import Circle, Line, RoundedRectangle, VGroup

from personajes.base import Personaje


class Demo(Personaje):
    """Unidad mecánica sobre ruedas, sin recursos gráficos externos."""
    CAMPOS = ("mano", "ctrl", "gesto")
    POSES = {
        "reposo": ((1.2, 1.1), (1.1, 1.7), (0, 0, 0)),
        "senala": ((1.7, 3.1), (1.2, 2.7), (0, 0, 0)),
        "explica": ((2.1, 1.8), (1.4, 2.6), (0, 0, 0)),
        "mira_abajo": ((1.6, 0.3), (1.3, 1.2), (0, 0, 0)),
        "jala": ((1.3, 0.1), (1.6, 1.1), (0, 0, 0)),
    }
    EXTRAS = dict(parpado=1.0, carga=0.0)
    MEDIO_ANCHO, ALTO = .8, 2.2
    HABLA = "demo"

    def __init__(self, pos=(0, -2), escala=1.0, pose="reposo"):
        super().__init__(pos, escala, pose)
        self.flotar = False
        self.refrescar()

    def _local(self, x, y):
        return np.array([x * self.e, y * self.e, 0.0])

    def _dibujar(self):
        def punto(xy):
            return [xy[0], xy[1], 0]
        cuerpo = RoundedRectangle(width=1.5, height=1.65, corner_radius=.18,
                                  fill_color="#253747", fill_opacity=1, stroke_color="#55D9CD").move_to([0, 1.25, 0])
        ruedas = [Circle(.22, color="#A9BBC8", fill_color="#253747", fill_opacity=1).move_to([x, .25, 0])
                  for x in (-.5, .5)]
        panel = RoundedRectangle(width=1.05, height=.4, corner_radius=.06, color="#55D9CD").move_to([0, 1.55, 0])
        indicador = Line([-.42, 1.55, 0], [-.42 + .84 * np.clip(float(self.carga), .01, 1.), 1.55, 0],
                         color="#55D9CD", stroke_width=6)
        brazo = VGroup(Line([.7, 1.8, 0], punto(self.ctrl), color="#D8E4EB", stroke_width=5),
                       Line(punto(self.ctrl), punto(self.mano), color="#D8E4EB", stroke_width=5))
        brazo.extremidad = True
        pinza = Circle(.12, color="#55D9CD", stroke_width=4).move_to(punto(self.mano))
        pinza.extremidad = True
        return VGroup(cuerpo, *ruedas, panel, indicador, brazo, pinza).scale(self.e, about_point=[0, 0, 0])

    def alcanzar(self, x, y):
        origen = self.punto(0, 0)
        matriz = np.column_stack(((self.punto(1, 0) - origen)[:2], (self.punto(0, 1) - origen)[:2]))
        mano = np.linalg.solve(matriz, np.array([x, y]) - origen[:2])
        return dict(mano=mano, ctrl=(mano + [.7, 1.8]) / 2)
