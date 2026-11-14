"""Clase base de los personajes articulados; cada diseño concreto hereda de aquí.

Idea: un personaje es un ESTADO (pose, posición, escala, mirada, boca…) y una función que lo dibuja. Cada vez que el
estado cambia, `refrescar()` vuelve a dibujar y copia los puntos sobre las mismas piezas (nunca se crean ni se quitan
piezas a mitad del video: ver Guía 5 §3.2).

Para crear un personaje nuevo basta con:
    class MiPersonaje(Personaje):
        POSES = {"reposo": (..., ...)}          # una tupla por pose, en el orden de CAMPOS
        CAMPOS = ("mano", "ctrl", "gesto")      # qué fija cada pose
        def _dibujar(self): ...                 # VGroup en el origen, ya escalado, SIEMPRE con las mismas piezas
        def _local(self, x, y): ...             # un punto del diseño en unidades de escena, respecto a su base
y hereda: poner(), anim(), ir_a(), punto(), espejo, aplastar, incl, y conectar() con boca, parpadeo y «hervor».
"""
import unicodedata

import numpy as np
from manim import *

_VOCAL = {"a": "a", "e": "m", "i": "m", "o": "o", "u": "o"}     # vocal -> forma de boca (a: abierta, m: media, o: redonda)


def visemas(palabra, max_formas=99):
    """Formas de boca de una palabra, en orden: una por vocal, y un cierre («c») en m, b y p.
    Si la palabra es muy corta para tantas formas, se quedan las más repartidas."""
    letras = unicodedata.normalize("NFD", palabra.lower())
    v = []
    for ch in letras:
        forma = _VOCAL.get(ch) or ("c" if ch in "mbp" else None)
        if forma and (not v or v[-1] != forma):
            v.append(forma)
    while v and v[-1] == "c":
        v.pop()
    v = v or ["m"]
    if len(v) > max_formas:          # no caben todas: primero se sacrifican los cierres, las vocales mandan
        v = [f for f in v if f != "c"] or ["m"]
    n = max(1, min(len(v), int(max_formas)))
    return [v[int(i * len(v) / n)] for i in range(n)]


class Personaje(VGroup):
    POSES = {}
    CAMPOS = ()                      # campos que fija una pose, en el orden de las tuplas de POSES
    DECIMALES = {}                   # redondeo de cada campo para decidir si hay que redibujar; None = no cuenta
    ANIM = dict(run_time=0.35, rate_func=rate_functions.ease_out_back)   # cómo se mueve al cambiar de pose
    HABLA = None                     # None: mueve la boca con cualquier palabra; "nombre": solo en los beats de ese personaje
    BOCA_PERIODO = 0.08              # tiempo mínimo de cada forma de boca (una palabra corta usa menos formas)
    EXTRAS = {"parpado": 1.0}        # estado que se anima pero que las poses no fijan (parpado: 1 = ojo normal)
    EXPRESIONES = {}                 # nombre -> dict(campos…, reposo="c"|"n"|"f"|"o"): ver anim(expresion=…)
    PARPADEO = (4.1, 0.12)           # cada cuántos segundos parpadea y cuánto dura
    HERVOR = 0.22                    # cada cuánto cambia el trazo (3 dibujos en bucle)
    VUELO = dict(altura=0.6, balanceo=9.0, vaiven=3.0)   # ir_a(modo="flota"): arco, inclinación y pequeño vaivén
    MEDIO_ANCHO, ALTO = 1.5, 3.6     # medio ancho y alto del CUERPO a escala 1 (sin el brazo), en unidades de escena

    def __init__(self, pos, escala=1.0, pose="reposo"):
        super().__init__()
        self.pos, self.e = np.array([pos[0], pos[1], 0.0]), escala
        self._fijar(pose)
        self.aplastar, self.incl, self.ojos, self.espejo = 1.0, 0.0, 1.0, False   # espejo: mira hacia el otro lado
        self.boca, self.semilla, self._clave, self._dibujos = "c", 0, None, {}
        self.reposo = "c"            # boca cuando no habla: c sonrisa, n neutra, f fastidio, o sorpresa
        self.flotar = True           # lo usan los personajes que flotan en reposo
        for campo, v in self.EXTRAS.items():
            setattr(self, campo, v)

    # ---------- lo que define cada personaje ----------
    def _dibujar(self):
        """Devuelve el VGroup del personaje en el origen, ya escalado, con SIEMPRE las mismas piezas en el mismo orden."""
        raise NotImplementedError

    def _local(self, x, y):
        """Un punto del diseño (coordenadas del SVG) en unidades de escena, respecto a la base del personaje."""
        raise NotImplementedError

    def _clave_extra(self):
        """Estado propio del personaje que también obliga a redibujar (tupla)."""
        return ()

    def _desplazamiento(self):
        """Desplazamiento extra del dibujo (p. ej. la respiración del personaje)."""
        return np.zeros(3)

    def _vivir(self, t):
        """Movimiento de reposo propio; se llama en cada fotograma desde conectar()."""

    # ---------- estado ----------
    @staticmethod
    def _valor(v):
        v = np.array(v, float)
        return float(v) if v.ndim == 0 else v

    def _fijar(self, pose):
        for campo, v in zip(self.CAMPOS, self.POSES[pose]):
            setattr(self, campo, self._valor(v))

    def _estado(self):
        d = {c: np.array(getattr(self, c), float) for c in (*self.CAMPOS, *self.EXTRAS)}
        d.update(pos=self.pos.copy(), e=np.array(float(self.e)), aplastar=np.array(float(self.aplastar)), incl=np.array(float(self.incl)))
        return d

    def _aplicar(self, d):
        for c, v in d.items():
            setattr(self, c, float(v) if np.ndim(v) == 0 else v)

    def _destino(self, pose=None, pos=None, escala=None, aplastar=None, incl=None, expresion=None, **campos):
        b = self._estado()
        if pose:
            for campo, v in zip(self.CAMPOS, self.POSES[pose]):
                b[campo] = np.array(v, float)
        if expresion:                # la expresión manda sobre el gesto de la pose
            for campo, v in self.EXPRESIONES[expresion].items():
                if campo != "reposo":
                    b[campo] = np.array(v, float)
        for campo, v in campos.items():
            if v is not None:
                b[campo] = np.array(v, float)
        if pos is not None:
            b["pos"] = np.array([pos[0], pos[1], 0.0])
        for clave, v in (("e", escala), ("aplastar", aplastar), ("incl", incl)):
            if v is not None:
                b[clave] = np.array(float(v))
        return b

    def _separar(self, kw):
        """Separa de kw los campos del personaje (p. ej. gesto=…) de las opciones de la animación (run_time=…)."""
        campos = {k: kw.pop(k) for k in list(kw) if k in self.CAMPOS or k in self.EXTRAS or k == "expresion"}
        return campos, kw

    def _reposo_de(self, campos):
        """Boca de reposo que trae la expresión pedida (None si no cambia)."""
        return self.EXPRESIONES[campos["expresion"]].get("reposo") if campos.get("expresion") else None

    # ---------- dibujo ----------
    def refrescar(self):
        partes = []
        for c in self.CAMPOS:
            dec = self.DECIMALES.get(c, 2)
            if dec is not None:
                v = getattr(self, c)
                partes.append(round(v, dec) if np.ndim(v) == 0 else tuple(np.round(v, dec)))
        partes += [round(getattr(self, c), 2) for c in self.EXTRAS]
        # El dibujo depende de `forma`; dónde se pone, de `sitio`. Un dibujo ya hecho se guarda en el origen y se
        # reutiliza: en reposo el personaje repite siempre los mismos (3 trazos × bocas × parpadeo), y respirar, flotar
        # o desplazarse sin cambiar de gesto solo mueve las piezas (tarea 8 de Fable: antes se redibujaba entero).
        forma = (round(self.e, 3), *partes, self.boca, self.semilla, self.ojos > 0.5,
                 round(self.aplastar, 3), round(self.incl, 2), self.espejo, *self._clave_extra())
        donde = self.pos + self._desplazamiento()
        clave = (forma, tuple(np.round(self.pos, 3)), tuple(np.round(donde, 4)))
        if clave != self._clave:
            self._clave = clave
            dibujo = self._dibujos.get(forma)
            if dibujo is None:
                g = self._dibujar()
                if self.espejo:
                    g.stretch(-1, 0, about_point=ORIGIN)
                if self.aplastar != 1.0:
                    g.stretch(self.aplastar, 1, about_point=ORIGIN)
                if self.incl:
                    g.rotate(np.radians(self.incl), about_point=ORIGIN)
                if not self.submobjects:
                    self.submobjects = list(g.submobjects)
                    self._piezas = self.family_members_with_points()
                    dibujo = [(p.points.copy(), p.get_stroke_width()) for p in self._piezas]
                else:
                    dibujo = [(p.points, p.get_stroke_width()) for p in g.family_members_with_points()]
                if len(self._dibujos) > 600:          # durante una animación cada fotograma es un dibujo nuevo
                    self._dibujos.clear()
                self._dibujos[forma] = dibujo
            # mismas piezas siempre: solo se copian los puntos (ya desplazados) y el grosor del trazo. Se recorren las
            # piezas CON puntos, también las que van dentro de un subgrupo (por ejemplo, las pupilas).
            for vieja, (puntos, grosor) in zip(self._piezas, dibujo):
                vieja.points = puntos + donde
                if vieja.stroke_width != grosor:
                    vieja.set_stroke(width=grosor)
        return self

    def punto(self, x, y):
        """Un punto del diseño (p. ej. su mano: `p.punto(*p.mano)`) en coordenadas de la escena, con escala, espejo,
        aplastado e inclinación. Sirve para que otro objeto siga a su mano o para colocarlo junto a algo."""
        v = np.array(self._local(x, y), float)
        v[1] *= self.aplastar
        if self.espejo:
            v[0] *= -1
        a = np.radians(self.incl)
        v = np.array([v[0] * np.cos(a) - v[1] * np.sin(a), v[0] * np.sin(a) + v[1] * np.cos(a), 0.0])
        return v + self.pos + self._desplazamiento()

    def caja_cuerpo(self):
        """[x0, y0, x1, y1] del cuerpo (sin el brazo). La usa la revisión de choques y senalar()."""
        w, h = self.MEDIO_ANCHO * self.e, self.ALTO * self.e * self.aplastar
        p = self.pos + self._desplazamiento()
        return [float(p[0] - w), float(p[1]), float(p[0] + w), float(p[1] + h)]

    def cajas_colision(self):
        """Cuerpo y cápsulas rectangulares pequeñas sobre los trazos reales de brazos/manos.

        No se usa la caja grande del brazo: el espacio vacío alrededor de una curva sigue libre.
        """
        cajas = [self.caja_cuerpo()]
        for parte in self.submobjects:
            if not getattr(parte, "extremidad", False):
                continue
            for m in parte.family_members_with_points():
                if max(m.get_fill_opacity(), m.get_stroke_opacity()) < 0.25:
                    continue
                if m.get_fill_opacity() >= 0.25:
                    if abs(m.get_center()[1]) < 20:
                        cajas.append([*m.get_corner(DL)[:2], *m.get_corner(UR)[:2]])
                elif m.get_stroke_opacity() >= 0.25:
                    margen = 0.01 * float(m.get_stroke_width()) + 0.012
                    for i in range(m.get_num_curves()):
                        pts = [m.get_nth_curve_function(i)(t) for t in np.linspace(0, 1, 5)]
                        for a, b in zip(pts, pts[1:]):
                            if max(abs(a[1]), abs(b[1])) < 20:
                                cajas.append([min(a[0], b[0])-margen, min(a[1], b[1])-margen,
                                              max(a[0], b[0])+margen, max(a[1], b[1])+margen])
        return [list(map(float, c)) for c in cajas]

    def senalar(self, objetivo, lado=None, hueco=0.25, pose="senala", limites=(-4.3, 3.05, -3.65, 6.2), ocupados=(), **kw):
        """Va JUNTO al objetivo (un objeto o un punto) y lo señala SIN taparlo: se coloca a un lado, con la punta de
        la mano a `hueco` del borde del objetivo y a su altura. `lado`: "izquierda" o "derecha" del objetivo; por
        defecto, el lado con más sitio. Devuelve la animación (como ir_a). Cambia `espejo` según el lado.
        `limites` = (x mín, x máx, y mín de su base, y máx): por defecto no baja a la franja de subtítulos."""
        if isinstance(objetivo, Mobject):
            c = [objetivo.get_left()[0], objetivo.get_bottom()[1], objetivo.get_right()[0], objetivo.get_top()[1]]
        else:
            c = [objetivo[0], objetivo[1], objetivo[0], objetivo[1]]
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        if pose == "auto":
            candidatos = []
            base_y = self.pos[1] + self._desplazamiento()[1]
            arriba = cy > base_y + self.ALTO*self.e + 0.6*self.e
            abajo = cy < base_y + 0.20*self.ALTO*self.e
            preferidas = ("senala",) if arriba else ("jala", "mira_abajo") if abajo else ("explica",)
            for nombre in ("senala", "explica", "mira_abajo", "jala"):
                if nombre not in self.POSES:
                    continue
                for costado in ((lado,) if lado else ("izquierda", "derecha")):
                    copia = self.copy()
                    copia.espejo = costado == "derecha"
                    # La animación todavía no ejecuta: su destino se obtiene con la misma geometría.
                    mano = np.array(copia._local(*self.POSES[nombre][0]), float)
                    alcance = max(self.MEDIO_ANCHO*self.e, abs(mano[0]))
                    x = c[0]-hueco-alcance if costado == "izquierda" else c[2]+hueco+alcance
                    w = self.MEDIO_ANCHO*self.e
                    pos = np.array([np.clip(x, limites[0]+w, limites[1]-w),
                                    np.clip(cy-mano[1], limites[2], limites[3]-self.ALTO*self.e), 0.0])
                    copia.poner(pose=nombre, pos=pos[:2])
                    def area(a, b):
                        return max(0, min(a[2],b[2])-max(a[0],b[0])) * max(0, min(a[3],b[3])-max(a[1],b[1]))
                    otras = [([*o.get_corner(DL)[:2], *o.get_corner(UR)[:2]] if isinstance(o, Mobject) else o) for o in ocupados]
                    choque = sum(area(a,b) for a in copia.cajas_colision() for b in otras)
                    choque += area(copia.caja_cuerpo(), c)
                    distancia = np.linalg.norm(pos-self.pos)
                    error_y = abs((pos+mano)[1]-cy)
                    direccion = 0 if nombre in preferidas else 10
                    candidatos.append((choque*1000+error_y*20+direccion+distancia, nombre, costado))
            if not candidatos:
                raise ValueError("El personaje no tiene poses para señalar automáticamente.")
            _, elegido, costado = min(candidatos)
            self.ultima_senal = dict(pose=elegido, lado=costado, candidatos=len(candidatos))
            return self.senalar(objetivo, costado, hueco, elegido, limites, ocupados=ocupados, **kw)
        mano = np.array(self._local(*self.POSES[pose][0]), float)      # la mano en esa pose, respecto a su base
        alcance = max(self.MEDIO_ANCHO * self.e, abs(mano[0]))
        if lado is None:
            lado = "izquierda" if (c[0] - limites[0]) >= (limites[1] - c[2]) else "derecha"
        self.espejo = lado == "derecha"                               # a la derecha del objetivo mira hacia la izquierda
        x = c[0] - hueco - alcance if lado == "izquierda" else c[2] + hueco + alcance
        w = self.MEDIO_ANCHO * self.e
        x = float(np.clip(x, limites[0] + w, limites[1] - w))
        y = float(np.clip(cy - mano[1], limites[2], limites[3] - self.ALTO * self.e))
        return self.ir_a([x, y], pose=pose, **kw)

    # ---------- vida propia ----------
    def conectar(self, escena, parpadeo=True, personaje=...):
        """Lo ata al reloj de la escena: la boca sigue a la voz, parpadea y el trazo «hierve».
        `personaje`: None = habla con cualquier palabra; "nombre" = solo en los beats de ese personaje."""
        quien = self.HABLA if personaje is ... else personaje
        palabras = escena.g.palabras if quien is None else [p for b in escena.g.beats if b.get("personaje") == quien for p in b["palabras"]]
        cada, dura = self.PARPADEO
        formas = {}                  # caché: palabra -> sus formas de boca

        def paso(m, dt):
            t = escena.t
            m.boca = m.reposo
            for i, p in enumerate(palabras):
                if p["t"] <= t <= p["t"] + p["d"]:
                    # la boca recorre las vocales de la palabra a lo largo de su duración (cierra en m, b, p)
                    v = formas.get(i) or formas.setdefault(i, visemas(p["w"], p["d"] / m.BOCA_PERIODO))
                    forma = v[min(int((t - p["t"]) / max(p["d"], 1e-6) * len(v)), len(v) - 1)]
                    m.boca = m.reposo if forma == "c" else forma
                    break
            m.semilla = int(t / m.HERVOR) % 3
            m.ojos = 0.0 if parpadeo and (t % cada) < dura else 1.0
            m._vivir(t)
            m.refrescar()
        self.add_updater(paso)
        return self

    # ---------- cambios ----------
    def poner(self, pose=None, pos=None, escala=None, aplastar=None, incl=None, **campos):
        """Cambia al instante (sin animar). Para cambios visibles usa anim()."""
        self.reposo = self._reposo_de(campos) or self.reposo
        self._aplicar(self._destino(pose, pos, escala, aplastar, incl, **campos))
        return self.refrescar()

    def anim(self, pose=None, pos=None, escala=None, aplastar=None, incl=None, **kw):
        """Animación hacia una pose o estado. Acepta también los campos del personaje (p. ej. gesto=(…)) y
        expresion="nombre" (ver EXPRESIONES). Mientras se mueve sigue hablando, parpadeando y «hirviendo»."""
        campos, kw = self._separar(kw)
        self._destino(pose, pos, escala, aplastar, incl, **campos)       # valida ya los argumentos
        reposo = self._reposo_de(campos)
        ab = []

        def f(mob, al):
            # Origen y destino se toman al EMPEZAR la animación, no al crearla: en un Succession
            # el segundo paso parte de donde dejó el primero y no devuelve a la postura previa.
            if not ab:
                ab[:] = [mob._estado(), mob._destino(pose, pos, escala, aplastar, incl, **campos)]
            a, b = ab
            if reposo:
                mob.reposo = reposo
            mob._aplicar({k: a[k] + (b[k] - a[k]) * al for k in a})
            mob.refrescar()
        # suspend_mobject_updating=False: sin esto Manim congela la boca, el parpadeo y el hervor durante el movimiento
        return UpdateFromAlphaFunc(self, f, **{**self.ANIM, "suspend_mobject_updating": False, **kw})

    def ir_a(self, pos, escala=None, modo="flota", pose=None, altura=None, **kw):
        """Desplazamiento a cualquier punto del cuadro. modo="flota": arco suave con leve balanceo;
        modo="camina": saltitos con aplastamiento al tocar el suelo. Termina con la pose y los campos indicados."""
        campos, kw = self._separar(kw)
        a = self._estado()
        b = self._destino(pose, pos, escala, 1.0, 0.0, **campos)
        reposo = self._reposo_de(campos)
        dx = b["pos"][0] - a["pos"][0]
        n = max(2, int(round(np.linalg.norm(b["pos"] - a["pos"]) / 0.7)))
        vuelo = self.VUELO
        altura = vuelo["altura"] if altura is None else altura

        def f(mob, al):
            if reposo:
                mob.reposo = reposo
            mob.flotar = modo != "camina"          # quien camina pisa el suelo: no flota hasta que vuelva a volar
            s = rate_functions.smooth(al)
            v = {k: a[k] + (b[k] - a[k]) * s for k in a}
            if modo == "camina":
                salto = abs(np.sin(n * PI * al))
                v["pos"] = v["pos"] + np.array([0, 0.22 * mob.e * salto, 0])
                v["aplastar"] = np.array(1.0 - 0.1 * (1 - salto) ** 6 * (0 < al < 1))
            else:
                v["pos"] = v["pos"] + np.array([0, altura * np.sin(PI * al), 0])
                v["incl"] = np.array(-vuelo["balanceo"] * np.sign(dx) * np.sin(PI * al) + vuelo["vaiven"] * np.sin(4 * PI * al))
            mob._aplicar(v)
            mob.refrescar()
        return UpdateFromAlphaFunc(self, f, **{"run_time": 1.0, "rate_func": linear, "suspend_mobject_updating": False, **kw})
