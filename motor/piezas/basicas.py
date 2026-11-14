"""Piezas sencillas: Taza, Gas (moléculas en una caja), Vaso y GraficoEnfriamiento."""

import json
import os
from pathlib import Path

import numpy as np
from manim import *
from manim.constants import CapStyleType, LineJointType

from nucleo import AMBAR, CALIENTE, FRIO, REDONDO, TIZA, nota, pildora, tiza


class Taza(VGroup):
    """Taza cuyo color sigue la temperatura: 1 = caliente (coral), 0 = fría (azul)."""

    def __init__(self, base, temp=1.0):
        super().__init__()
        x, y = base
        self.asa = tiza(Circle(radius=0.27, stroke_color=TIZA, stroke_width=7).move_to([x + 0.55, y + 0.5, 0]), 3)
        self.cuerpo = tiza(RoundedRectangle(corner_radius=0.14, width=0.95, height=1.05, stroke_color=TIZA,
                                            stroke_width=7, fill_opacity=1).move_to([x, y + 0.53, 0]), 5)
        self.vapor = VGroup(*[
            tiza(VMobject(stroke_color=CALIENTE, stroke_width=5, **REDONDO).set_points_smoothly(
                [[x + dx, y + 1.25, 0], [x + dx - 0.12, y + 1.5, 0], [x + dx + 0.06, y + 1.75, 0], [x + dx - 0.06, y + 2.0, 0]]), 7 + i)
            for i, dx in enumerate((-0.18, 0.2))])
        self.add(self.asa, self.cuerpo, self.vapor)
        self.set_temp(temp)

    def set_temp(self, c):
        self.temp = c
        self.cuerpo.set_fill(interpolate_color(ManimColor(FRIO), ManimColor(CALIENTE), c), opacity=0.9)
        self.vapor.set_stroke(opacity=max(0.0, 2 * c - 1))
        return self


class Gas(VGroup):
    """Moléculas en una caja con dos mitades. temp 1 = rápida y coral, 0 = lenta y azul.
    Al poner `mezclar = True` las velocidades se igualan (equilibrio térmico)."""

    def __init__(self, caja=(-3.7, 3.7, 0.7, 5.0), n=18, semilla=4):
        super().__init__()
        self.caja, self.pared, self.mezclar, self.congelado = caja, True, False, False
        x0, x1, y0, y1 = caja
        rng = np.random.default_rng(semilla)
        self.pos = np.vstack([np.column_stack([rng.uniform(x0 + .3, -.3, n), rng.uniform(y0 + .3, y1 - .3, n)]),
                              np.column_stack([rng.uniform(.3, x1 - .3, n), rng.uniform(y0 + .3, y1 - .3, n)])])
        ang = rng.uniform(0, TAU, 2 * n)
        self.dir = np.column_stack([np.cos(ang), np.sin(ang)])
        self.temp = np.array([1.0] * n + [0.0] * n)
        self.puntos = VGroup(*[Dot(radius=0.12) for _ in range(2 * n)])
        self.marco = tiza(RoundedRectangle(corner_radius=0.15, width=x1 - x0, height=y1 - y0, stroke_color=TIZA,
                                           stroke_width=6).move_to([(x0 + x1) / 2, (y0 + y1) / 2, 0]), 2)
        self.muro = tiza(DashedLine([0, y0, 0], [0, y1, 0], stroke_color=TIZA, stroke_width=6, dash_length=0.2), 4)
        self.add(self.puntos, self.marco, self.muro)
        self.add_updater(lambda m, dt: m.paso(dt))
        self.paso(0)

    def paso(self, dt):
        x0, x1, y0, y1 = self.caja
        if self.mezclar:
            self.temp += (self.temp.mean() - self.temp) * min(1, 1.6 * dt)
        if not self.congelado:
            antes = self.pos[:, 0].copy()
            self.pos += self.dir * (0.7 + 4.3 * self.temp)[:, None] * dt
            for eje, (lo, hi) in enumerate(((x0 + .15, x1 - .15), (y0 + .15, y1 - .15))):
                fuera = (self.pos[:, eje] < lo) | (self.pos[:, eje] > hi)
                self.dir[fuera, eje] *= -1
                self.pos[:, eje] = np.clip(self.pos[:, eje], lo, hi)
            if self.pared:
                cruza = (antes * self.pos[:, 0] < 0) | (np.abs(self.pos[:, 0]) < 0.15)
                self.dir[cruza, 0] = np.sign(antes[cruza]) * np.abs(self.dir[cruza, 0])
                self.pos[cruza, 0] = np.sign(antes[cruza]) * 0.16
        for d, p, c in zip(self.puntos, self.pos, self.temp):
            d.move_to([p[0], p[1], 0]).set_fill(interpolate_color(ManimColor(FRIO), ManimColor(CALIENTE), float(c)), 1)


class Vaso(VGroup):
    """Vaso de vidrio con agua. `base` = centro del fondo; `nivel` 0-1 (fracción de la altura); `marca` = nivel anterior
    marcado con tiza y la nota «antes» (None = sin marca). El agua es tiza translúcida: NO usa colores de temperatura."""

    def __init__(self, base, alto=2.2, ancho=1.3, nivel=0.85, marca=None, nota_marca="antes", lado_nota=LEFT):
        super().__init__()
        self.base, self.alto, self.ancho = np.array([base[0], base[1], 0.0]), alto, ancho
        self.nivel = nivel
        self.agua = Polygon(*self._esquinas(nivel), stroke_width=0, fill_color=TIZA, fill_opacity=0.13)
        self.superficie = Line(*self._borde(nivel), stroke_color=TIZA, stroke_width=4, stroke_opacity=0.85)
        x0, y0 = self.base[0], self.base[1]
        cuerpo = VMobject(stroke_color=TIZA, stroke_width=7, **REDONDO).set_points_as_corners(
            [[x0 - ancho / 2, y0 + alto, 0], [x0 - 0.42 * ancho, y0, 0], [x0 + 0.42 * ancho, y0, 0], [x0 + ancho / 2, y0 + alto, 0]])
        brillo = Line([x0 - 0.36 * ancho, y0 + 0.2 * alto, 0], [x0 - 0.4 * ancho, y0 + 0.8 * alto, 0], stroke_color=TIZA, stroke_width=4, stroke_opacity=0.35)
        self.add(self.agua, self.superficie, tiza(cuerpo, 2), brillo)
        self.marca = VGroup()
        if marca is not None:
            a, b = self._borde(marca)
            raya = DashedLine(a + LEFT * 0.12, b + RIGHT * 0.12, stroke_color=AMBAR, stroke_width=5, dash_length=0.1)
            self.marca = VGroup(raya, nota(nota_marca, AMBAR, 26).next_to(a if lado_nota is LEFT else b, lado_nota, buff=0.18))
            self.add(self.marca)

    def _borde(self, n):
        x0, y0, h, w = self.base[0], self.base[1], self.alto, self.ancho
        medio = (0.42 + 0.08 * n) * w     # las paredes se abren hacia arriba
        return np.array([x0 - medio, y0 + n * h, 0]), np.array([x0 + medio, y0 + n * h, 0])

    def _esquinas(self, n):
        x0, y0, w = self.base[0], self.base[1], self.ancho
        a, b = self._borde(n)
        return [np.array([x0 - 0.42 * w + 0.04, y0 + 0.04, 0]), np.array([x0 + 0.42 * w - 0.04, y0 + 0.04, 0]), b + LEFT * 0.04, a + RIGHT * 0.04]

    def set_nivel(self, n):
        self.nivel = n
        self.agua.set_points_as_corners([*self._esquinas(n), self._esquinas(n)[0]])
        self.superficie.put_start_and_end_on(*self._borde(n))
        return self

    def llevar(self, base, alto, **kw):
        """Animación: mueve y escala el vaso para que su fondo quede en `base` con altura `alto`. El grosor del trazo y
        el tamaño de la nota «antes» no cambian (siguen pareciendo tiza a cualquier escala)."""
        f = alto / self.alto
        b0, b1 = self.base.copy(), np.array([base[0], base[1], 0.0])
        nota_m = self.marca[1] if len(self.marca) > 1 else None
        partes = [sm for sm in self.family_members_with_points() if nota_m is None or sm not in nota_m.family_members_with_points()]
        orig = [sm.points.copy() for sm in partes]
        lado = LEFT if nota_m is not None and nota_m.get_center()[0] < self.marca[0].get_center()[0] else RIGHT

        def g(m, a):
            k = 1 + (f - 1) * a
            b = b0 + (b1 - b0) * a
            for sm, p in zip(partes, orig):
                sm.points = b + k * (p - b0)
            if nota_m is not None:
                nota_m.next_to(m.marca[0], lado, buff=0.12)
        self.base, self.alto, self.ancho = b1, alto, self.ancho * f
        return UpdateFromAlphaFunc(self, g, **{"run_time": 0.8, "rate_func": rate_functions.smooth, **kw})

    def bajar(self, hasta, **kw):
        """Animación del nivel (el «tiempo acelerado» se rotula aparte)."""
        n0 = self.nivel
        return UpdateFromAlphaFunc(self, lambda m, a: m.set_nivel(n0 + (hasta - n0) * a), **{"run_time": 1.5, "rate_func": linear, **kw})


class GraficoEnfriamiento(VGroup):
    """Patrón "con el tiempo…" (Guía 2 §2): curva T contra tiempo relativo t/τ que se dibuja sola.
    Modelo de Newton T = Ta + (T0 − Ta)·e^(−x), con x = t/τ. Lleva SIEMPRE el rótulo «modelo aproximado»
    y no muestra minutos. `self.x` (ValueTracker) es hasta dónde va dibujada;
    la barra ámbar marca la diferencia T − Ta en la punta y se encoge con ella."""

    def __init__(self, T0=80, Ta=24, x_max=4.0, origen=(-3.0, 0.9), ancho=5.9, alto=4.3, t_min=15, t_max=88):
        super().__init__()
        self.T0, self.Ta, self.x_max = T0, Ta, x_max
        ox, oy = origen
        self.P = lambda x, T: np.array([ox + ancho * x / x_max, oy + alto * (T - t_min) / (t_max - t_min), 0])
        self.T = lambda x: Ta + (T0 - Ta) * np.exp(-x)
        ejes = tiza(VGroup(Arrow([ox, oy, 0], [ox, oy + alto + 0.35, 0], buff=0, stroke_width=6, color=TIZA, tip_length=0.22),
                           Arrow([ox, oy, 0], [ox + ancho + 0.3, oy, 0], buff=0, stroke_width=6, color=TIZA, tip_length=0.22)), 2)
        self.ejes = ejes
        self.et_T = nota("T", TIZA, 34).next_to([ox, oy + alto + 0.35, 0], LEFT, buff=0.15)
        self.et_t = nota("tiempo relativo, t/τ", TIZA, 24).next_to([ox + ancho, oy, 0], DOWN, buff=0.18).align_to([ox + ancho + 0.3, 0, 0], RIGHT)
        self.rotulo = pildora("modelo aproximado", AMBAR, 24).move_to([ox + ancho - 1.35, oy + alto + 0.3, 0])
        self.ambiente = tiza(DashedLine(self.P(0, Ta), self.P(x_max, Ta), stroke_color=FRIO, stroke_width=5, dash_length=0.16), 4)
        self.et_amb = nota("ambiente: 24 °C", FRIO, 24).next_to(self.P(x_max, Ta), UP, buff=0.12).align_to(self.P(x_max, Ta), RIGHT)
        self.p0 = pildora(f"{T0} °C", CALIENTE, 26).next_to(self.P(0, T0), RIGHT, buff=0.2)
        self.x = ValueTracker(0.0)
        self.curva = VMobject(stroke_color=CALIENTE, stroke_width=9, **REDONDO)
        self.barra = Line(self.P(0, T0), self.P(0, Ta), stroke_color=AMBAR, stroke_width=10, **REDONDO)
        self.punta = Dot(self.P(0, T0), radius=0.1, color=CALIENTE)

        def paso(m, dt):
            xf = max(self.x.get_value(), 1e-3)
            xs = np.linspace(0, xf, 60)
            m.curva.set_points_smoothly([self.P(x, self.T(x)) for x in xs])
            c = interpolate_color(ManimColor(FRIO), ManimColor(CALIENTE), (self.T(xf) - Ta) / (T0 - Ta))
            m.punta.move_to(self.P(xf, self.T(xf))).set_color(c)
            m.barra.put_start_and_end_on(self.P(xf, self.T(xf)) + 0.001 * UP, self.P(xf, Ta))
        self.add(self.ambiente, self.ejes, self.et_T, self.et_t, self.et_amb, self.curva, self.barra, self.punta, self.rotulo)
        self.add_updater(paso)
        paso(self, 0)

    def dibujar(self, hasta=None, **kw):
        return self.x.animate(**{"run_time": 1.5, "rate_func": rate_functions.linear, **kw}).set_value(self.x_max if hasta is None else hasta)

    def tramo(self, x0, x1, color=AMBAR):
        """Resalta un tramo de la curva (para que el narrador lo señale)."""
        xs = np.linspace(x0, x1, 30)
        return VMobject(stroke_color=color, stroke_width=20, stroke_opacity=0.45, **REDONDO).set_points_smoothly(
            [self.P(x, self.T(x)) for x in xs])
