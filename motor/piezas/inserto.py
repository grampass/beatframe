"""Insertos gráficos: «escenarios aparte» que se ponen encima de la escena atenuada (con enfocar()).

BorradorMensaje: el campo de un mensaje sin enviar. Cabecera, UNA frase a la vez, trazos que
sugieren un texto largo, cursor que parpadea y ▶ apagado (el mensaje no sale). Sin nombres, fotos, marcas ni historial.
Lleva `inserto = True`: la revisión de composición cuenta sus textos (presupuesto, tamaño, glifos) pero no avisa de que
tapa al personaje, porque lo hace a propósito. NO usar `no_revisar` para esto (deja de contarse todo).
Uso:
    b = BorradorMensaje(self)
    self.plano.poner(b, "borrador")                                   # o una zona propia
    self.en("b4", "escribí", self.enfocar_anim(b), FadeIn(b))         # aparece sobre la escena atenuada
    self.hasta(g.t_palabra("b5", "En") - .15); b.escribir("Quería decirte algo…", lineas=3)
    self.play(FadeIn(b.texto), FadeIn(b.lineas, lag_ratio=.3))         # cambia JUSTO antes de la palabra
    self.play(self.desenfocar_anim(), FadeOut(b))
"""
from manim import *

from nucleo import AMBAR, FUENTE, GRIS, LILA, TIZA, tiza


class BorradorMensaje(VGroup):
    def __init__(self, escena, cabecera="borrador", ancho=6.4, alto=3.3, tam=32):
        super().__init__()
        self.inserto = True
        self.tam = tam
        self.marco = tiza(RoundedRectangle(corner_radius=.22, width=ancho, height=alto, stroke_color=TIZA, stroke_width=5,
                                           fill_color="#1B1F27", fill_opacity=1), 7)
        self.cab = Text(cabecera, font=FUENTE, font_size=26, color=LILA).move_to([-ancho / 2 + .85, alto / 2 - .32, 0])
        self.campo = RoundedRectangle(corner_radius=.14, width=ancho - .5, height=alto - .95, stroke_color=GRIS,
                                      stroke_width=3, fill_color="#232838", fill_opacity=1).shift(DOWN * .2)
        self.enviar = Triangle(stroke_width=0, fill_color=GRIS, fill_opacity=1).rotate(-PI / 2).scale(.13) \
            .move_to([ancho / 2 - .45, alto / 2 - .32, 0])
        self.texto, self.lineas = VGroup(), VGroup()
        self.cursor = Line(UP * .2, DOWN * .2, stroke_color=AMBAR, stroke_width=5)
        self.add(self.marco, self.cab, self.campo, self.enviar, self.texto, self.lineas, self.cursor)
        self._x0 = self.campo.get_left()[0] + .3
        self._y0 = self.campo.get_top()[1] - .38
        self.cursor.move_to([self._x0, self._y0, 0])
        self.cursor.add_updater(lambda m, dt: m.set_stroke(opacity=1. if int(escena.t / .45) % 2 == 0 else 0.))

    def _origen(self):
        """Esquina de escritura en coordenadas actuales (el grupo puede haberse movido o escalado con plano.poner)."""
        return self.campo.get_left()[0] + .3 * self.campo.width / 5.9, self.campo.get_top()[1] - .38 * self.campo.height / 2.35

    def escribir(self, frase="", lineas=0):
        """Sustituye el contenido AL INSTANTE (para animarlo, FadeIn(b.texto) / FadeIn(b.lineas) después)."""
        x0, y0 = self._origen()
        k = self.campo.width / 5.9
        self.texto.remove(*self.texto.submobjects)
        if frase:
            t = Text(frase, font=FUENTE, font_size=self.tam, color=TIZA).scale(k)
            if t.width > self.campo.width - .6 * k:
                t.scale_to_fit_width(self.campo.width - .6 * k)
            self.texto.add(t.move_to([x0, y0, 0], aligned_edge=LEFT))
        self.lineas.remove(*self.lineas.submobjects)
        self.lineas.add(*[Line([x0, y0 - (.5 + .36 * i) * k, 0], [x0 + (4.8, 4.1, 2.6)[i % 3] * k, y0 - (.5 + .36 * i) * k, 0],
                               stroke_color=GRIS, stroke_width=7) for i in range(lineas)])
        if lineas:
            fin = self.lineas[-1].get_right()
        elif frase:
            fin = self.texto[0].get_right()
            fin[1] = y0
        else:
            fin = [x0 - .12, y0, 0]
        self.cursor.move_to([fin[0] + .12, fin[1], 0])
        return self

    def vaciar(self):
        return self.escribir("", 0)


def globo_vacio(centro, ancho=2.1, alto=1.25):
    """Silueta de globo de diálogo SIN texto: una respuesta imaginada, nunca una respuesta real."""
    x, y = centro
    cuerpo = Ellipse(width=ancho, height=alto, stroke_color=TIZA, stroke_width=5).move_to([x, y, 0])
    cola = Polygon([x + .45, y - .5, 0], [x + .95, y - .95, 0], [x + .75, y - .42, 0], stroke_color=TIZA, stroke_width=5)
    return tiza(VGroup(cuerpo, cola), 11).set_fill(opacity=0)
