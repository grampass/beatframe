"""Ranuras de pantalla: la escena pide una ZONA con nombre, no una coordenada.

Cada composición reparte el cuadro vertical (9 × 16; x de -4.5 a 4.5, y de -8 a 8) en zonas que no se pisan.
Así dos objetos solo chocan si alguien los pone en la misma zona, y eso se ve al leer la escena.

    self.plano = Plano("laboratorio")
    self.plano.poner(perfil, "lateral")                 # lo encoge si hace falta para que quepa, y lo centra
    self.plano.fila("condiciones", chip1, chip2)        # los reparte en fila; salta de línea si no caben
    self.rotulo("perfil esquemático", hasta="b6")       # la ÚNICA aclaración visible (EscenaEstudio)

Zonas comunes a todas las composiciones:
    titulo        barra de progreso y título (las pone el motor)
    condiciones   píldoras con las condiciones del experimento («temperatura constante»)
    espectador    el cuadro pequeño de un personaje que observa
    principal     lo que se explica: la vista, la ecuación, el objeto grande
    lateral       el apoyo de lo principal: un perfil, un gráfico, una leyenda
    rotulo        UNA línea de aclaración (la gestiona self.rotulo)
    apoyo         objetos secundarios: vaso pequeño, control deslizante
    personaje     el sitio del especialista cuando no está actuando; ahí no se escribe
    subtitulos    los subtítulos (los pone el motor; nada más entra ahí)
Debajo de y = -4.8 y a la derecha de x = 3.15 las plataformas tapan la imagen: ninguna zona llega ahí.

Para ver las zonas dibujadas sobre el video: variable de entorno PLANO_VER=1.
"""
import os

import numpy as np
from manim import *
from zonas import perfil as datos_perfil, caja_conservadora

# (x0, x1, y0, y1) de cada zona
_COMUN = {
    "titulo": (-4.2, 4.2, 6.35, 7.5),
    "condiciones": (-4.2, 1.05, 4.7, 6.32),
    "espectador": (1.25, 3.05, 4.78, 6.13),
    "subtitulos": (-3.9, 3.1, -4.65, -3.75),
}
COMPOSICIONES = {
    # vista grande a la izquierda, columna lateral a la derecha y el personaje debajo de ella
    "laboratorio": {**_COMUN,
                    "principal": (-4.15, 1.05, -1.85, 4.65),
                    "lateral": (1.25, 3.1, -1.25, 4.65),
                    "rotulo": (-4.15, 1.05, -2.66, -2.14),
                    "apoyo": (-4.15, 0.9, -3.7, -2.74),
                    "personaje": (1.2, 3.1, -3.65, -1.35)},
    # una ecuación o un objeto grande en el centro; la vista anterior, reducida, arriba a la izquierda
    "ecuacion": {**_COMUN,
                 "miniatura": (-4.15, -0.6, 1.6, 4.65),
                 "personaje": (-0.3, 3.1, 1.6, 4.65),
                 "principal": (-4.0, 3.1, -1.2, 1.4),
                 "rotulo": (-4.0, 3.1, -1.95, -1.35),
                 "lateral": (-4.0, 3.1, -2.7, -2.05),
                 "apoyo": (-4.15, 3.1, -3.65, -2.8)},
    # Pizarra: la explicación grande y el narrador pequeño abajo a la izquierda
    "pizarra": {**_COMUN,
                "principal": (-4.0, 3.1, 0.2, 4.65),
                "lateral": (-0.9, 3.1, -3.6, -0.5),
                "rotulo": (-4.0, 3.1, -0.45, 0.15),
                "apoyo": (-0.9, 3.1, -3.6, -0.5),
                "personaje": (-4.2, -1.1, -4.6, -0.6),
                "subtitulos": (-0.9, 3.1, -4.65, -3.75)},
    # Plano de sobremesa: personaje grande y objetos en la superficie de apoyo
    "mesa": {**_COMUN,
             "principal": (-4.0, 3.1, 1.9, 4.65),
             "rotulo": (-4.0, 3.1, 0.3, 0.9),
             "subtitulos": (-3.9, 3.1, 0.95, 1.85),
             "personaje": (-3.2, 1.4, -3.1, 0.2),
             "lateral": (1.5, 3.1, -3.1, 0.2),
             "apoyo": (-4.2, 3.1, -4.6, -3.15)},
}


class Plano:
    def __init__(self, composicion="laboratorio", perfil="legado"):
        if composicion not in COMPOSICIONES:
            raise ValueError(f"No existe la composición «{composicion}». Hay: {', '.join(COMPOSICIONES)}")
        self.nombre, self.zonas = composicion, dict(COMPOSICIONES[composicion])
        self.perfil = datos_perfil(perfil)
        self.zonas["segura"] = caja_conservadora(perfil)

    def caja(self, zona):
        """(x0, x1, y0, y1) de la zona."""
        if zona not in self.zonas:
            raise ValueError(f"La composición «{self.nombre}» no tiene la zona «{zona}». Tiene: {', '.join(self.zonas)}")
        return self.zonas[zona]

    def centro(self, zona):
        x0, x1, y0, y1 = self.caja(zona)
        return np.array([(x0 + x1) / 2, (y0 + y1) / 2, 0.0])

    def tam(self, zona):
        x0, x1, y0, y1 = self.caja(zona)
        return x1 - x0, y1 - y0

    @property
    def sub_y(self):
        """Altura de los subtítulos en esta composición (para self.sub_y)."""
        return float(self.centro("subtitulos")[1])

    def poner(self, mob, zona, alinear=ORIGIN, margen=0.08, min_escala=0.7, llenar=False):
        """Coloca `mob` dentro de la zona. Lo encoge si no cabe (nunca por debajo de `min_escala`: si haría falta,
        se detiene con un mensaje, porque un objeto ilegible no es una solución). `alinear`: ORIGIN centra; LEFT, UP,
        UL… lo pegan a ese borde. `llenar=True` también lo agranda hasta ocupar la zona."""
        ancho, alto = self.tam(zona)
        ancho, alto = ancho - 2 * margen, alto - 2 * margen
        if mob.width <= 0 or mob.height <= 0:
            return mob.move_to(self.centro(zona))
        f = min(ancho / mob.width, alto / mob.height)
        if f < 1 or llenar:
            if f < min_escala:
                raise ValueError(f"«{zona}» ({self.nombre}) mide {ancho:.1f} × {alto:.1f} y el objeto {mob.width:.1f} × {mob.height:.1f}: "
                                 f"habría que reducirlo al {f * 100:.0f} %. Acorta el texto, pártelo o usa otra zona.")
            mob.scale(f)
        x0, x1, y0, y1 = self.caja(zona)
        mob.move_to(self.centro(zona))
        a = np.array(alinear, float)
        if a[0]:
            mob.set_x((x0 + margen + mob.width / 2) if a[0] < 0 else (x1 - margen - mob.width / 2))
        if a[1]:
            mob.set_y((y0 + margen + mob.height / 2) if a[1] < 0 else (y1 - margen - mob.height / 2))
        return mob

    def fila(self, zona, *mobs, buff=0.1, margen=0.03):
        """Reparte varios objetos (p. ej. píldoras) en filas dentro de la zona, de arriba abajo y de izquierda a
        derecha. Si entre todos no caben, se detiene con un mensaje."""
        x0, x1, y0, y1 = self.caja(zona)
        x, y, alto_fila = x0 + margen, y1 - margen, 0.0
        for m in mobs:
            if m.width > x1 - x0 - 2 * margen:
                raise ValueError(f"Un objeto de {m.width:.1f} de ancho no cabe en «{zona}» ({x1 - x0:.1f}). Acórtalo.")
            if x + m.width > x1 - margen + 1e-6:        # salta de fila
                x, y, alto_fila = x0 + margen, y - alto_fila - buff, 0.0
            m.move_to([x + m.width / 2, y - m.height / 2, 0])
            x, alto_fila = x + m.width + buff, max(alto_fila, m.height)
        if y - alto_fila < y0 - 1e-6:
            raise ValueError(f"Los {len(mobs)} objetos no caben en «{zona}» ({self.nombre}): sobran {y0 - (y - alto_fila):.2f} de alto. "
                             "Une dos en uno o pasa alguno al rótulo.")
        return VGroup(*mobs)

    def libre(self, zona, objetos, margen=0.0):
        """¿La zona no toca ninguna de las cajas dadas? (útil antes de mandar ahí al personaje)."""
        x0, x1, y0, y1 = self.caja(zona)
        return not any(c[0] < x1 - margen and c[2] > x0 + margen and c[1] < y1 - margen and c[3] > y0 + margen for c in objetos)

    def ver(self):
        """Las zonas dibujadas (para depurar la composición). Se añade sola a la escena con PLANO_VER=1."""
        g = VGroup()
        for nombre, (x0, x1, y0, y1) in self.zonas.items():
            r = Rectangle(width=x1 - x0, height=y1 - y0, stroke_color="#FF2D55", stroke_width=2, stroke_opacity=0.8,
                          fill_color="#FF2D55", fill_opacity=0.06).move_to([(x0 + x1) / 2, (y0 + y1) / 2, 0])
            t = Text(nombre, font="Arial", font_size=18, color="#FF2D55").move_to(r.get_corner(UL) + np.array([0.08, -0.08, 0]), aligned_edge=UL)
            g.add(r, t)
        return g


VER = os.environ.get("PLANO_VER", "") == "1"
