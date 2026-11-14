"""Núcleo del motor: paleta, lienzo, Guion, trazo de tiza, utilidades (píldora, nota, pop, latir, aparecer,
desaparecer) y EscenaEstudio (reloj, audio, barra, título, subtítulos, cambio de página).

No importa personajes ni piezas: todo lo demás depende de este módulo, nunca al revés.
Calidad: variable de entorno CALIDAD=baja renderiza a 540x960 y 15 fps para previsualizar rápido.
"""

import json
import os
import zlib
from pathlib import Path

import numpy as np
from manim import *
from manim.constants import CapStyleType, LineJointType

import choques
import plano as _plano
from plano import Plano

RAIZ = Path(__file__).resolve().parent.parent
from configuracion import CONFIG, ruta
ASSETS = ruta("assets", Path(__file__).resolve().parent / "recursos")
_VISUAL = CONFIG.get("visual", {})

# ---------- Paleta oficial (perfil editorial) ----------
FONDO = _VISUAL.get('FONDO', '#000000')
PAGINA = _VISUAL.get('PAGINA', '#181818')
TIZA = _VISUAL.get('TIZA', '#FFFFFF')
GRIS = _VISUAL.get('GRIS', '#808080')
CALIENTE = _VISUAL.get('CALIENTE', '#FF0000')
FRIO = _VISUAL.get('FRIO', '#0000FF')
AMBAR = _VISUAL.get('AMBAR', '#FFBF00')
MORADO = _VISUAL.get('MORADO', '#800080')
MORADO_OSC = _VISUAL.get('MORADO_OSC', '#400040')
LILA = _VISUAL.get('LILA', '#C8A2C8')
ROSA = _VISUAL.get('ROSA', '#FF80C0')
COLORES = {"caliente": CALIENTE, "frio": FRIO, "ambar": AMBAR, "morado": LILA, "tiza": TIZA}

# ---------- Lienzo vertical ----------
BAJA = os.environ.get("CALIDAD", "alta") == "baja"
config.pixel_width = 540 if BAJA else 1080
config.pixel_height = 960 if BAJA else 1920
config.frame_rate = 15 if BAJA else 30
config.frame_height = 16
config.frame_width = 9
config.background_color = FONDO

FUENTE = _VISUAL.get('FUENTE', 'Arial')
FUENTE_MANO = _VISUAL.get('FUENTE_MANO', 'Arial')
REDONDO = dict(cap_style=CapStyleType.ROUND, joint_type=LineJointType.ROUND)

# Zona segura (perfil editorial): nada importante con y < Y_MIN ni x > X_MAX
Y_MIN, X_MAX = _VISUAL.get("Y_MIN", -8.0), _VISUAL.get("X_MAX", 4.5)
Y_MESA = _VISUAL.get('Y_MESA', 0.0)  # borde superior de la mesa en fondo_mesa.png


# =====================================================================
# Guion
# =====================================================================
class Guion:
    def __init__(self, carpeta: Path, pausa=0.22, inicio=0.15):
        datos = json.loads((carpeta / "guion.json").read_text(encoding="utf-8"))
        tiempos = json.loads((carpeta / "audio" / "tiempos.json").read_text(encoding="utf-8"))
        self.titulo = datos["titulo"]
        self.ajustes_receta = datos.get("ajustes_receta", {}) or {}      # recetas.aplicar_receta los aplica solos
        self.beats, self.palabras, t = [], [], inicio
        for b in datos["beats"]:
            pal = [dict(p, t=p["t"] + t) for p in tiempos[b["id"]]]
            dur = tiempos[b["id"]][-1]["t"] + tiempos[b["id"]][-1]["d"] + 0.12 + b.get("cola", 0)
            self.beats.append(dict(b, archivo=carpeta / "audio" / f"{b['id']}.mp3", ini=t, fin=t + dur, palabras=pal))
            self.palabras += pal
            t += dur + pausa
        self.total = t
        self._por_id = {b["id"]: b for b in self.beats}

    def __getitem__(self, bid):
        return self._por_id[bid]

    def t_palabra(self, bid, palabra, n=0):
        """Instante en que se pronuncia la n-ésima aparición de `palabra` en el beat."""
        hits = [p["t"] for p in self[bid]["palabras"] if p["w"].lower().strip("¿?¡!.,") == palabra.lower()]
        if not hits:
            raise KeyError(f"'{palabra}' no está en el beat {bid}: {[p['w'] for p in self[bid]['palabras']]}")
        return hits[n]


# =====================================================================
# Trazo de tiza
# =====================================================================
def temblor(mob, semilla=0, amp=0.03, densidad=3):
    """Desplaza los puntos con un campo suave: el trazo deja de ser perfecto, como dibujado a mano."""
    for sm in mob.family_members_with_points():
        if densidad and sm.get_num_curves() < 40:
            sm.insert_n_curves(sm.get_num_curves() * (densidad - 1))
        p = sm.points.copy()
        x, y, k = p[:, 0] / amp, p[:, 1] / amp, semilla
        p[:, 0] += amp * (np.sin(0.13 * y + 1.9 * k) + 0.5 * np.sin(0.31 * x + 0.7 * k))
        p[:, 1] += amp * (np.cos(0.11 * x + 2.3 * k) + 0.5 * np.sin(0.29 * y + 1.3 * k))
        sm.points = p
    return mob


def tiza(mob, semilla=1):
    return temblor(mob, semilla=semilla, amp=0.035)


# =====================================================================
# Componentes
# =====================================================================
def fondo(nombre):
    img = ImageMobject(str(ASSETS / nombre))
    img.scale_to_fit_width(9)
    return img


def fondo_mesa():
    """Devuelve (fondo, frente). Dibuja al personaje ENTRE los dos para que quede detrás de la mesa."""
    atras = fondo("fondo_mesa.png")
    frente = fondo("fondo_mesa_frente.png")
    frente.move_to([0, -8 + frente.height / 2, 0])
    return atras, frente


def pildora(texto, color=AMBAR, tam=34):
    t = Text(texto, font=FUENTE, font_size=tam, color=color)
    caja = RoundedRectangle(corner_radius=(t.height + 0.3) / 2, width=t.width + 0.6, height=t.height + 0.3,
                            stroke_color=color, stroke_width=5, fill_color=FONDO, fill_opacity=0.95)
    g = VGroup(tiza(caja, semilla=len(texto)), t)
    g.importante, g.nombre = True, f"la píldora «{texto}»"     # la revisión de choques cuenta su borde
    return g


def nota(texto, color=AMBAR, tam=30):
    return Text(texto, font=FUENTE_MANO, font_size=tam, color=color)


def etiqueta(texto, color=TIZA, tam=22, op=1.0):
    """Texto suelto para rotular algo, con borde del color del fondo para que se lea sobre cualquier cosa.
    Tamaño mínimo 20 (menos no se lee en un teléfono). Para subíndices usa MathTex: la fuente no los tiene."""
    if tam < choques.TAM_MIN:
        raise ValueError(f"etiqueta «{texto}»: tamaño {tam} menor que el mínimo ({choques.TAM_MIN}). Acorta el texto en vez de encogerlo.")
    if any(ch in choques.GLIFOS_DUDOSOS for ch in texto):
        raise ValueError(f"etiqueta «{texto}»: la fuente no tiene subíndices, superíndices ni «·»; usa MathTex u otro signo.")
    t = Text(texto, font=FUENTE, font_size=tam, color=color)
    t.set_opacity(op)
    return t.set_stroke(FONDO, width=8, background=True)


def pop(mob, **kw):
    a = GrowFromCenter(mob, rate_func=rate_functions.ease_out_back, **{"run_time": 0.3, **kw})
    a.sonido_motor = "rotulo"
    return a


# ---------- Dibujo vivo: bucles de 3 fotogramas ----------
def latir(mob, escena, variantes, periodo=0.22, desfase=0.0):
    """Hace que `mob` alterne en bucle entre los dibujos de `variantes` (mobjects con la MISMA estructura que mob,
    p. ej. copias con otra semilla de tiza o con la forma algo cambiada). Solo se copian puntos: no se crean piezas."""
    pts = [[sm.points.copy() for sm in v.family_members_with_points()] for v in variantes]
    mob._k = -1

    def paso(m, dt):
        k = int((escena.t + desfase) / periodo) % len(pts)
        if k != m._k:
            m._k = k
            for sm, q in zip(m.family_members_with_points(), pts[k]):
                sm.points = q
    mob.add_updater(paso)
    paso(mob, 0)
    return mob


class Esquema(VGroup):
    """Dibujo explicativo por PARTES que entran en momentos distintos (2026-11-14).
    Se dibuja en coordenadas locales: `self.parte("ondas", mob)` registra cada parte (visible=True la añade ya) y
    `colocar(escala, centro)` escala y mueve TODAS, también las que aún no se han añadido. Así una parte que entra
    después (FadeIn(esq.ondas), Create(...)) cae en su sitio y no a escala 1 en el origen."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.partes = {}

    def parte(self, nombre, mob, visible=False):
        if nombre in self.partes:
            raise ValueError(f"Esquema: la parte «{nombre}» ya existe")
        if hasattr(self, nombre):
            raise ValueError(f"Esquema: «{nombre}» choca con un atributo de VGroup; usa otro nombre")
        self.partes[nombre] = mob
        setattr(self, nombre, mob)
        if visible:
            self.add(mob)
        return mob

    def colocar(self, escala=1.0, centro=(0.0, 0.0)):
        mover = lambda m: m.scale(escala, about_point=ORIGIN).shift([centro[0], centro[1], 0])
        dentro = {id(m) for m in self.get_family()}
        for m in self.partes.values():
            if id(m) not in dentro:          # las de dentro ya se transforman con el grupo
                mover(m)
        mover(self)
        return self


def instante_corte(inicios, t, margen=0.1, deriva=0.2):
    """Instante para cambiar de plano en un diálogo: `margen` s antes del beat siguiente, a mitad de la pausa, cuando
    el subtítulo anterior ya se fue y el siguiente aún no entra. Devuelve None si no hay que esperar (inicio del video,
    ya pasado o no queda beat). `deriva`: a 15 fps el reloj real puede ir unas centésimas por delante del beat."""
    if t <= 0.01:
        return None
    sig = [i for i in inicios if i > t - deriva]
    if not sig or min(sig) - margen <= t:
        return None
    return min(sig) - margen


def sugerir_palabra(palabras, t_desde, fin, antes=0.15, min_dur=0.15):
    """La palabra más tardía del beat en la que una animación de `min_dur` aún cabe antes de `fin` sin esperar a
    antes de `t_desde`. None si no hay ninguna. Para el aviso de retraso de EscenaEstudio.en()."""
    validas = [p["w"].strip("¿?¡!.,…") for p in palabras if p["t"] - antes >= t_desde - 1e-6 and fin - (p["t"] - antes) >= min_dur]
    return validas[-1] if validas else None


def _opacidades(mob):
    return [(sm, sm.get_fill_opacity(), sm.get_stroke_opacity(), sm.get_stroke_opacity(background=True))
            for sm in mob.family_members_with_points()]


def aparecer(mob, **kw):
    """Fundido de entrada que NO añade el objeto a la escena. Úsalo con objetos que viven DENTRO de otro grupo que ya
    está en escena (p. ej. rótulos fijados a escenario): FadeIn/Create los añadirían sueltos y Manim partiría el grupo
    padre en pedazos, que dejarían de actualizarse (Guía 5 §4)."""
    datos = _opacidades(mob)

    def f(m, a):
        for sm, fo, so, bo in datos:
            sm.set_fill(opacity=fo * a)
            sm.set_stroke(opacity=so * a)
            sm.set_stroke(opacity=bo * a, background=True)
    f(mob, 0)
    return UpdateFromAlphaFunc(mob, f, **{"run_time": 0.4, **kw})


def desaparecer(mob, **kw):
    """Inverso de aparecer(): deja el objeto transparente (sigue en su grupo; quítalo después si hace falta)."""
    datos = _opacidades(mob)

    def f(m, a):
        for sm, fo, so, bo in datos:
            sm.set_fill(opacity=fo * (1 - a))
            sm.set_stroke(opacity=so * (1 - a))
            sm.set_stroke(opacity=bo * (1 - a), background=True)
    return UpdateFromAlphaFunc(mob, f, **{"run_time": 0.4, **kw})


# =====================================================================
# Escena base
# =====================================================================
class CamaraEstudio(Camera):
    """Cámara del estudio: dibuja lo mismo que la de Manim, pero más rápido.
    1. No dibuja lo que no se ve: objetos aparcados fuera de cuadro (así se ocultan las piezas: Guía 5 §3.2) y objetos
       del todo transparentes. Por ejemplo, las letras de subtítulos que aún no se muestran.
       «Fuera de cuadro» se decide con la caja de TODOS los puntos del objeto contra el encuadre real de la cámara,
       ampliado por el grosor del trazo (antes miraba solo el primer y el último punto y perdía objetos que cruzan).
    2. No recalcula un fondo PNG que no cambió: guarda su imagen ya colocada y la reutiliza. La clave cubre todos los
       píxeles (zlib.adler32), la posición y el encuadre, así que cualquier cambio de la imagen se ve.
    Exactitud: motor/pruebas_motor.py compara esta cámara con la de Manim píxel a píxel (Guía 5 §5)."""

    # Encuadre (EscenaEstudio.encuadre, 2026-11-13): la escena se dibuja ampliada `zoom` veces hacia `centro`; el HUD
    # (ids en `fijos`) y los objetos con `.fijo = True` se dibujan con el encuadre normal. Con zoom 1 no cambia nada.
    zoom, centro, fijos = 1.0, None, frozenset()

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._fondos = {}

    def capture_mobjects(self, mobjects, **kw):
        if abs(self.zoom - 1.0) < 1e-6 or self.centro is None:
            return super().capture_mobjects(mobjects, **kw)
        mobjects = list(mobjects)
        # Se separa POR PIEZAS: una pieza del HUD metida en otro grupo tampoco se amplía (el título salía duplicado)
        fijos = {id(f) for m in mobjects if id(m) in self.fijos or getattr(m, "fijo", False) for f in m.get_family()}
        todos = self.get_mobjects_to_display(mobjects, **kw)
        kw = dict(kw, include_submobjects=False)
        escena = [m for m in todos if id(m) not in fijos]
        hud = [m for m in todos if id(m) in fijos]
        fw, fh, fc = self.frame_width, self.frame_height, self.frame_center
        self.frame_width, self.frame_height, self.frame_center = fw / self.zoom, fh / self.zoom, np.asarray(self.centro, dtype=float)
        self.pixel_array_to_cairo_context = {}          # el contexto de Cairo guarda la transformación: rehacerlo
        try:
            super().capture_mobjects(escena, **kw)
        finally:
            self.frame_width, self.frame_height, self.frame_center = fw, fh, fc
            self.pixel_array_to_cairo_context = {}
        if hud:
            super().capture_mobjects(hud, **kw)

    @staticmethod
    def _opaco(m):
        try:
            if m.fill_rgbas[:, 3].max() > 0:
                return True
            if m.stroke_width > 0 and m.stroke_rgbas[:, 3].max() > 0:
                return True
            return bool(m.background_stroke_width > 0 and m.background_stroke_rgbas[:, 3].max() > 0)
        except Exception:
            return True

    def _en_cuadro(self, vms):
        """Para cada VMobject con puntos, ¿su caja (todos los puntos, más el grosor del trazo) toca el encuadre?
        Vectorizado: una sola pasada de numpy para todos los objetos del fotograma."""
        largos = np.fromiter((len(m.points) for m in vms), dtype=np.int64, count=len(vms))
        inicios = np.concatenate(([0], np.cumsum(largos)[:-1]))
        pts = np.concatenate([m.points for m in vms])[:, :2]
        mins = np.minimum.reduceat(pts, inicios, axis=0)
        maxs = np.maximum.reduceat(pts, inicios, axis=0)
        k = self.cairo_line_width_multiple
        margen = np.fromiter((max(m.stroke_width, m.background_stroke_width) * k for m in vms),
                             dtype=float, count=len(vms))
        cx, cy = self.frame_center[0], self.frame_center[1]
        mw, mh = self.frame_width / 2, self.frame_height / 2
        return ~((maxs[:, 0] + margen < cx - mw) | (mins[:, 0] - margen > cx + mw)
                 | (maxs[:, 1] + margen < cy - mh) | (mins[:, 1] - margen > cy + mh))

    def get_mobjects_to_display(self, *a, **kw):
        mobs = super().get_mobjects_to_display(*a, **kw)
        vms = [m for m in mobs if isinstance(m, VMobject) and len(m.points)]
        dentro = set()
        if vms:
            dentro = {id(m) for m, d in zip(vms, self._en_cuadro(vms)) if d and self._opaco(m)}
        return [m for m in mobs if not isinstance(m, VMobject) or id(m) in dentro]

    def display_image_mobject(self, image_mobject, pixel_array):
        pa = image_mobject.get_pixel_array()
        clave = (image_mobject.points.tobytes(), zlib.adler32(np.ascontiguousarray(pa)), pa.shape,
                 pixel_array.shape, tuple(np.asarray(self.frame_center, dtype=float)), self.frame_width,
                 self.frame_height, image_mobject.resampling_algorithm)
        guardado = self._fondos.get(id(image_mobject))
        if guardado is not None and guardado[0] == clave:
            return self.overlay_PIL_image(pixel_array, guardado[1])
        capturadas, original = [], self.overlay_PIL_image

        def capturar(pa, img):
            capturadas.append(img)
            return original(pa, img)
        self.overlay_PIL_image = capturar
        try:
            super().display_image_mobject(image_mobject, pixel_array)
        finally:
            del self.overlay_PIL_image
        if capturadas:
            self._fondos[id(image_mobject)] = (clave, capturadas[0])


from manim.renderer.cairo_renderer import CairoRenderer


class RenderizadorComposicion(CairoRenderer):
    """Recorre animaciones y updaters, sin rasterizar ni depender del plan de salida de Manim."""
    def update_skipping_status(self):
        super().update_skipping_status()
        self.skip_animations = True

    def update_frame(self, *a, **kw):
        return

    def render(self, *a, **kw):
        return


class EscenaEstudio(Scene):
    carpeta: Path = None
    t = 0.0

    def __init__(self, *a, **kw):
        kw.setdefault("camera_class", CamaraEstudio)
        if os.environ.get("SOLO_CHOQUES") == "1" and "renderer" not in kw:
            kw["renderer"] = RenderizadorComposicion(camera_class=kw.pop("camera_class"), skip_animations=True)
        super().__init__(*a, **kw)

    # Reloj: self.t es el tiempo real del video, leído de renderer.time (avanza con cada fotograma escrito). Se pone
    # al día al empezar la actualización de cada fotograma, antes que cualquier objeto. NO acumular dt: Manim pierde
    # un fotograma de dt por animación y la imagen se atrasaría respecto a la voz. Tampoco sumar last_t.
    # Antes lo llevaba un objeto «reloj» con updater, puesto el primero de la escena; eso hacía que Manim tratara
    # TODO como móvil y redibujara también el fondo en cada fotograma (tarea 8 de Fable).
    def update_mobjects(self, dt):
        self.t = self.renderer.time + 1 / config.frame_rate
        super().update_mobjects(dt)

    def get_time_progression(self, run_time, description, n_iterations=None, override_skip_animations=False):
        if os.environ.get("SOLO_CHOQUES") == "1" and getattr(self, "_registro", None) is not None:
            from tqdm import tqdm
            # Cairo ya sumó run_time al saltar la animación. Se restaura el reloj al terminar cada muestra.
            self._sondeo_inicio = self.renderer.time - run_time
            n = max(4, min(64, int(np.ceil(run_time / 0.25))))
            tiempos = set(np.linspace(0, run_time, n + 1))
            for p in self.g.palabras:
                for marca in (p["t"], p["t"] + p["d"]):
                    t = marca - self._sondeo_inicio
                    if 0 < t < run_time:
                        tiempos.add(t)
            return tqdm(sorted(tiempos), disable=True)
        return super().get_time_progression(run_time, description, n_iterations, override_skip_animations)

    def play_internal(self, skip_rendering=False):
        return super().play_internal(skip_rendering=skip_rendering or os.environ.get("SOLO_CHOQUES") == "1")

    def update_to_time(self, t):
        virtual = os.environ.get("SOLO_CHOQUES") == "1" and hasattr(self, "_sondeo_inicio")
        fin = self.renderer.time
        if virtual:
            self.renderer.time = self._sondeo_inicio + t
        try:
            super().update_to_time(t)
            if getattr(self, "_registro", None) is not None:
                sub = getattr(self._hud[-1], "actual", None) if getattr(self, "_hud", None) else None
                if virtual or self.renderer.time >= getattr(self, "_proxima_foto", -1) or sub != getattr(self, "_ultimo_sub", None):
                    self._foto()
                    self._proxima_foto, self._ultimo_sub = self.renderer.time + 0.25, sub
        finally:
            if virtual:
                self.renderer.time = fin
    sub_y = 1.15            # altura de los subtítulos; cámbiala al cambiar de escenario

    def setup(self):
        # Reloj: self.t es el tiempo real del video, leído de renderer.time (avanza con cada fotograma
        # escrito). NO acumular dt: Manim pierde un fotograma de dt por animación y la imagen se
        # atrasaría respecto a la voz. Tampoco sumar last_t: contaría el tiempo dos veces.
        self.g = Guion(self.carpeta)
        self._retrasos = []
        self._revision_dir = Path(os.environ.get("REVISION_DIR") or Path(self.carpeta) / "revision")
        from sonido import PistaSonora
        self._sonora = PistaSonora(self.g, activo=os.environ.get("SONIDO") == "1")
        self._sonora.cargar(Path(self.carpeta) / "sonido.json")
        for b in self.g.beats:
            self.add_sound(str(b["archivo"]), time_offset=b["ini"])
        self._hud = [self._barra(), self._titulo(), self._subtitulos()]
        self.add_foreground_mobjects(*self._hud)
        # --- composición y revisión automática (Guía 2 §6 y Guía 5 §0) ---
        self.plano = None                       # self.plano = Plano("laboratorio") en la escena
        self._rotulo, self._rotulo_hasta, self._plano_visto = None, None, False
        self._registro = None if os.environ.get("SIN_CHOQUES") == "1" else choques.Registro()
        # --- render por tramos: BEATS=b6-b8 (o BEATS=b6) dibuja solo esos beats; el resto se salta ---
        self._tramo, self._saltando = None, False
        tramo = os.environ.get("BEATS", "").strip()
        if tramo:
            a, _, b = tramo.partition("-")
            self._tramo = (self.g[a]["ini"], self.g[b or a]["fin"])
            if self._tramo[0] > 0.3:
                self.next_section(skip_animations=True)
                self._saltando = True
        if os.environ.get("SOLO_CHOQUES") == "1":      # producir.py --choques: recorre la escena sin dibujarla
            self.next_section(skip_animations=True)
            self._tramo = None
        self._vigila = True

    def fin_voz(self):
        """Segundo en que termina la ÚLTIMA voz real (inicio de su beat + duración del mp3). Puede pasar de g.total:
        el mp3 trae una cola de silencio que el guion no cuenta."""
        from sonido import duraciones_video
        fin = 0.0
        for b in self.g.beats:
            try:
                fin = max(fin, b["ini"] + duraciones_video(b["archivo"]).get("audio", 0.0))
            except Exception:                       # sin ffprobe o sin archivo: lo vigila producir.py
                pass
        return fin

    def cubrir_voz(self):
        """Alarga la imagen hasta el final de la última voz (antes había que poner self.wait(0.3) a mano al final de
        cada escena: si no, producir.py paraba con «audio ausente o duración desalineada»). La llama tear_down."""
        if self.carpeta is None or getattr(self, "_tramo", None) is not None or os.environ.get("SOLO_CHOQUES") == "1":
            return 0.0
        falta = self.fin_voz() - self.renderer.time
        if falta > 1.5 / config.frame_rate:
            self.wait(falta)
            return falta
        return 0.0

    def corte(self, margen=0.1):
        """Cambio de plano limpio entre personajes (diálogos): espera hasta `margen` s antes del beat siguiente.
        Llamarlo ANTES de montar el plano nuevo. Evita el subtítulo de uno sobre el plano del otro (se ve a 30 fps) y
        tolera que a 15 fps el reloj vaya unas centésimas por delante (antes, un min() vacío rompía el render)."""
        t = instante_corte([b["ini"] for b in self.g.beats], self.renderer.time, margen)
        if t is not None:
            self.hasta(t)

    def montar(self, receta, *objetos, tocados=(), corte=True, poner=None, **ajustes):
        """Plano de un personaje en UNA línea (diálogos, 2026-11-14): corte limpio a mitad de la pausa, receta con los
        ajustes del guion («ajustes_receta») y los de aquí, y los MISMOS objetos de la mesa en el mismo sitio en cada
        vuelta (los que el personaje toca, en `tocados`). `poner`: pose inicial del personaje, p. ej.
        dict(gesto=MIRA_CUADERNO). Devuelve el montaje (montaje.personaje, montaje.escenario)."""
        from recetas import aplicar_receta, objetos_en_mesa
        if corte:
            self.corte()
        montaje = aplicar_receta(self, receta, **ajustes)
        if objetos or tocados:
            sueltos = [o for o in objetos if not any(o is t for t in tocados)]
            objetos_en_mesa(self, montaje, *sueltos, *tocados, tocados=tocados)
        if poner:
            montaje.personaje.poner(**poner)
        return montaje

    def tear_down(self):
        if getattr(self, "g", None) is not None:
            self.cubrir_voz()
        super().tear_down()
        if self._registro is not None and self.carpeta is not None:
            self._registro.guardar(self._revision_dir / "choques.json")
        if self.carpeta is not None and getattr(self, "_sonora", None) is not None:
            self._sonora.guardar(self._revision_dir / "sonido-eventos.json")
        if self.carpeta is not None:
            from artefactos import escribir_json
            escribir_json(self._revision_dir / "tiempos-escena.json", dict(retrasos=self._retrasos, total=self.renderer.time))

    def sonido(self, nombre, db=-22, instante=None, clave=None):
        """Efecto en el reloj del video. Se mezcla después; solo activo con producir.py --sonido.
        Si cae después del final del guion (una animación en la cola), se omite con un aviso: no detiene el render."""
        son = getattr(self, "_sonora", None)
        if son is None:
            return
        t = self.renderer.time if instante is None else instante
        if son.activo and t > son.g.total:
            print(f"[AVISO] efecto «{nombre}» en t={t:.2f} s, después del final del guion ({son.g.total:.2f} s): no se mezcla")
            return
        son.efecto(nombre, t, db, clave)

    def pista(self, ruta, db=0.0, instante=None, atenuar=True):
        """Pista de ARCHIVO propia de la producción (p. ej. la música de cierre) en el reloj del video. `ruta` relativa a la
        carpeta del video. Se comprueba siempre que cabe entera antes del final (si no, error); se mezcla con --sonido."""
        son = getattr(self, "_sonora", None)
        if son is None:
            return
        ruta = Path(ruta)
        if not ruta.is_absolute():
            ruta = Path(self.carpeta) / ruta
        son.archivo(ruta, self.renderer.time if instante is None else instante, db, atenuar)

    # ----- Encuadre: acercamientos de cámara con el HUD fijo -----
    MARCO = (4.5, 8.0)      # medio ancho y medio alto del cuadro (unidades de escena)

    def estado_camara(self, t=None):
        """(zoom, centro) en el instante t según los encuadres programados. El centro se limita para que el cuadro ampliado
        no enseñe nada fuera del escenario."""
        planos = getattr(self, "_planos", None)
        if not planos:
            return 1.0, np.zeros(3)
        t = self.renderer.time if t is None else t
        z, c = 1.0, np.zeros(3)
        for t0, d, z1, c1 in planos:
            if t < t0:
                break
            a = 1.0 if d <= 0 else rate_functions.ease_in_out_sine(min(1.0, (t - t0) / d))
            z, c = z + (z1 - z) * a, c + (c1 - c) * a
        mx, my = self.MARCO[0] * (1 - 1 / z), self.MARCO[1] * (1 - 1 / z)
        return z, np.array([np.clip(c[0], -mx, mx), np.clip(c[1], -my, my), 0.0])

    def encuadre(self, zoom=1.0, centro=(0.0, 0.0), dur=1.0, desde=None):
        """Acercamiento suave de cámara (o vuelta al plano general con zoom=1) que empieza en `desde` (por defecto, ahora)
        y dura `dur`. NO bloquea: la animación sigue. Título, barra y subtítulos no se mueven; un inserto con `.fijo = True`
        tampoco. La revisión de composición mide en coordenadas de PANTALLA durante el acercamiento."""
        if not np.isfinite(zoom) or zoom < 1 or not np.isfinite(dur) or dur < 0 or not np.isfinite(centro[:2]).all():
            raise ValueError("Encuadre: zoom finito ≥ 1, duración no negativa y centro finito")
        if desde is not None and (not np.isfinite(desde) or desde < 0):
            raise ValueError("Encuadre: inicio finito no negativo")
        if not hasattr(self, "_planos"):
            self._planos = []
            cam = self.camera

            def mover(m, dt):
                cam.zoom, cam.centro = self.estado_camara()
                cam.fijos = frozenset(id(h) for h in self._hud)
            self._reloj_camara = Mobject().add_updater(mover)
            self.mobjects.insert(0, self._reloj_camara)    # primero: con él todo se redibuja en cada fotograma
        t0 = self.renderer.time if desde is None else float(desde)
        self._planos.append((t0, float(dur), float(zoom), np.array([centro[0], centro[1], 0.0])))
        self._planos.sort(key=lambda p: p[0])

    def ambiente(self, nombre, db=-30, hasta=None):
        """Inicia ambiente de escenario y cierra el anterior. `nombre=None` lo corta (silencio de ambiente).
        No se llama dentro de un updater."""
        son = getattr(self, "_sonora", None)
        if son is None:
            return
        if nombre is None:
            son.callar(self.renderer.time)
        else:
            son.ambiente(nombre, self.renderer.time, hasta, db)

    # ----- Vigilancia: animaciones que partirían un grupo vivo (Guía 5 §4) -----
    def _padre_vivo(self, mob):
        """Si `mob` vive DENTRO de un objeto de la escena que tiene updaters, devuelve ese objeto. Añadirlo suelto
        (FadeIn, Create, Write, add) o quitarlo (FadeOut) partiría al grupo y lo dejaría congelado."""
        if any(top is mob for top in self.mobjects):
            return None
        for top in self.mobjects:
            if any(m is mob for m in top.get_family()):
                return top if top.get_family_updaters() else None
        return None

    def _vigilar(self, anim, convertir=True):
        if not isinstance(anim, Animation):
            return anim
        for sub in getattr(anim, "animations", None) or ():
            self._vigilar(sub, convertir=False)
        entra, sale = bool(getattr(anim, "introducer", False)), bool(getattr(anim, "remover", False))
        if not (entra or sale):
            return anim
        padre = self._padre_vivo(anim.mobject)
        if padre is None:
            return anim
        simple = type(anim) in (FadeIn, FadeOut) and np.allclose(getattr(anim, "shift_vector", 0), 0) and getattr(anim, "scale_factor", 1) == 1
        if convertir and simple:      # se puede hacer lo mismo sin sacar el objeto de su grupo
            f = aparecer if entra else desaparecer
            return f(anim.mobject, run_time=anim.run_time, rate_func=anim.rate_func)
        raise ValueError(f"{type(anim).__name__} sobre un objeto que vive dentro de {type(padre).__name__}: Manim lo sacaría del grupo y "
                         f"{type(padre).__name__} quedaría congelado. Usa aparecer(obj) / desaparecer(obj), o Circumscribe para resaltar (Guía 5 §4).")

    def play(self, *args, **kw):
        if getattr(getattr(self, "_sonora", None), "activo", False):
            from sonido import ambientes_animacion, marcas_animacion
            ambientes = []
            for anim in args:
                if isinstance(anim, Animation):
                    for nombre, desfase in marcas_animacion(anim, kw.get("run_time")):
                        self.sonido(nombre, instante=self.renderer.time + desfase)
                    ambientes.extend(ambientes_animacion(anim, kw.get("run_time")))
            for nombre, desfase in sorted(ambientes, key=lambda a: a[1]):
                instante = self.renderer.time + desfase
                if nombre is None:
                    self._sonora.callar(instante)
                else:
                    self._sonora.ambiente(nombre, instante)
        if getattr(self, "_vigila", False):
            self._ventana()
            self._foto()                 # el estado justo antes de cada animación también lo vio el espectador
            args = [self._vigilar(a) for a in args]
        return super().play(*args, **kw)

    def add(self, *mobs):
        if getattr(self, "_vigila", False):
            for m in mobs:
                padre = self._padre_vivo(m)
                if padre is not None:
                    raise ValueError(f"self.add() de un objeto que vive dentro de {type(padre).__name__}: lo partiría y quedaría congelado. "
                                     "Añade el grupo entero, o cambia el orden de capas con set_z_index().")
        return super().add(*mobs)

    # ----- Revisión de la composición -----
    def _beat_actual(self):
        t = self.renderer.time
        return next((b["id"] for b in self.g.beats if b["ini"] - 0.05 <= t <= b["fin"] + 0.05), None)

    def _foto(self):
        """Revisa la composición en este instante (solapes, zonas tapadas, textos pequeños): motor/choques.py."""
        if _plano.VER and self.plano is not None and not self._plano_visto:
            guia = self.plano.ver()
            for m in guia.get_family():
                m.no_revisar = True
            self.add_foreground_mobjects(guia)
            self._plano_visto = True
        if self._registro is not None:
            self._registro.foto(self, self._beat_actual(), Y_MIN, X_MAX)

    def _ventana(self):
        """Render por tramos (BEATS): entra y sale del modo «saltar» al cruzar los límites del tramo."""
        if self._tramo is None:
            return
        t = self.renderer.time
        if self._saltando and self._tramo[0] - 0.02 <= t < self._tramo[1] - 0.02:
            self.next_section(skip_animations=False)
            self._saltando = False
            if self._registro is not None:
                self._registro.inicio_tramo = float(t)      # segundo del guion en que empieza el video del tramo
        elif not self._saltando and t >= self._tramo[1] - 0.02:
            self.next_section(skip_animations=True)
            self._saltando = True

    # ----- Rótulo único: la aclaración vigente (una sola a la vez) -----
    def rotulo_anim(self, texto=None, hasta=None, color=TIZA, tam=24):
        """Animaciones para relevar el rótulo (para meterlas en un self.play con otras). Ver rotulo()."""
        anterior = self._rotulo
        anims = [FadeOut(anterior)] if anterior is not None else []
        self._rotulo, self._rotulo_hasta = None, None
        if texto:
            t = etiqueta(texto, color, tam)
            (self.plano or Plano("laboratorio")).poner(t, "rotulo")
            self._rotulo, self._rotulo_hasta = t, hasta
            entrada = FadeIn(t)
            entrada.sonido_motor = "rotulo"
            # Mismo tiempo total que el relevo paralelo; solo una aclaración legible a la vez.
            anims = [Succession(FadeOut(anterior), entrada, run_time=1.0)] if anterior is not None else [entrada]
        return anims

    def rotulo(self, texto=None, hasta=None, color=TIZA, tam=24, run_time=0.25):
        """Muestra la ÚNICA aclaración de la pantalla en la ranura «rotulo» de self.plano. Si ya había una, la releva.
        `hasta="b6"`: se quita sola al terminar ese beat. `self.rotulo()` sin texto la quita.
        Todas las aclaraciones («modelo aproximado», «perfil esquemático»…) van aquí: nunca hay dos a la vez."""
        anims = self.rotulo_anim(texto, hasta, color, tam)
        if anims:
            self.play(*anims, run_time=run_time)

    # ----- Tiempo: animar justo en una palabra, sin pasarse -----
    def en(self, bid, palabra, *anims, antes=0.15, tope=None, run_time=0.4, min_dur=0.15, n=0, **kw):
        """Espera a la palabra y ejecuta las animaciones ENCAJADAS en el hueco que queda hasta `tope`
        (otra marca: (bid, palabra); por defecto, el final del beat). Si el hueco es menor que `run_time`, las acorta;
        si ni así caben (menos de `min_dur`), avisa con el beat y la palabra."""
        desde = self.renderer.time
        self.hasta(self.g.t_palabra(bid, palabra, n) - antes)
        fin = (self.g.t_palabra(*tope) - 0.05) if tope else self.g[bid]["fin"]
        hueco = fin - self.renderer.time
        if hueco < min_dur:
            otra = sugerir_palabra(self.g[bid]["palabras"], desde, fin, antes, min_dur)
            pista = f"; prueba anclarla en «{otra}»" if otra and otra.lower() != palabra.lower() else ""
            self._retrasos.append(dict(beat=bid, palabra=palabra, t=float(fin), retraso=float(min_dur - hueco),
                                       sugerencia=otra))
            print(f"[AVISO] vas {min_dur - hueco:.2f} s tarde respecto a t={fin:.2f} (en «{palabra}» de {bid} no caben las animaciones{pista})")
        self.play(*anims, run_time=max(min_dur, min(run_time, hueco)), **kw)

    # ----- HUD -----
    def _barra(self, y=7.35, x0=-4.0, x1=4.0, hueco=0.12):
        beats, grupo = self.g.beats, VGroup()
        ancho = (x1 - x0 - hueco * (len(beats) - 1)) / len(beats)
        for i, b in enumerate(beats):
            a = x0 + i * (ancho + hueco)
            # Barra discreta (pedido del usuario): fina y atenuada, para que no compita con la explicación
            grupo.add(Line([a, y, 0], [a + ancho, y, 0], stroke_color=GRIS, stroke_width=4, stroke_opacity=0.55, **REDONDO))
            lleno = Line([a, y, 0], [a + 0.01, y, 0], stroke_color=TIZA, stroke_width=4, **REDONDO)

            def paso(m, dt, a=a, b=b):
                f = float(np.clip((self.t - b["ini"]) / (b["fin"] - b["ini"]), 0, 1))
                m.put_start_and_end_on([a, y, 0], [a + max(0.01, f * ancho), y, 0]).set_stroke(opacity=0.45 if f > 0 else 0)
            lleno.add_updater(paso)
            grupo.add(lleno)
        return grupo

    def _titulo(self):
        t = Text(self.g.titulo, font=FUENTE, font_size=34, color=AMBAR)
        if t.width > 7.8:
            t.scale_to_fit_width(7.8)
        return t.move_to([0, 6.72, 0])

    def _subtitulos(self, max_palabras=3, max_letras=15, tam=58):
        eventos = []
        for b in self.g.beats:
            claves = {k.lower(): COLORES[v] for k, v in b.get("claves", {}).items()}
            bloques, actual = [], []
            for i, p in enumerate(b["palabras"]):
                pausa = actual and p["t"] - (actual[-1]["t"] + actual[-1]["d"]) > 0.22
                largo = sum(len(q["w"]) + 1 for q in actual) + len(p["w"])
                if actual and (len(actual) == max_palabras or largo > max_letras or pausa):
                    # Una negación nunca cierra un bloque: debe acompañar a su verbo.
                    # Pasa al bloque siguiente, junto a su verbo.
                    arrastre = []
                    if len(actual) > 1 and actual[-1]["w"].lower().strip("¿?¡!.,…") in ("no", "ni", "sin", "nunca"):
                        arrastre = [actual.pop()]
                    bloques.append(actual)
                    actual = arrastre
                actual.append(p)
            bloques.append(actual)
            for bl in bloques:
                textos = [q["w"].upper() for q in bl]
                for j, p in enumerate(bl):
                    txt = Text(" ".join(textos), font=FUENTE, font_size=tam, color=TIZA)
                    ini = sum(len(x) for x in textos[:j])
                    txt[ini:ini + len(textos[j])].set_color(claves.get(p["w"].lower().strip("¿?¡!.,"), AMBAR))
                    if txt.width > 7.6:
                        txt.scale_to_fit_width(7.6)
                    txt.set_stroke(FONDO, width=14, background=True)
                    fin = bl[j + 1]["t"] if j + 1 < len(bl) else p["t"] + p["d"] + 0.18
                    eventos.append((p["t"], fin, txt))
        # Todos los textos existen desde el inicio, aparcados fuera de cuadro; el activo se trae a su sitio.
        # Se conserva la estructura de los grupos durante toda la animación.
        APARCADO = [0, 60, 0]
        sub = VGroup(*[txt.move_to(APARCADO) for _, _, txt in eventos])
        sub.actual = None

        def paso(m, dt):
            idx = next((i for i, (a, b, _) in enumerate(eventos) if a <= self.t < b), None)
            clave = (idx, self.sub_y)
            if clave != m.actual:
                if m.actual and m.actual[0] is not None:
                    m[m.actual[0]].move_to(APARCADO)
                if idx is not None:
                    m[idx].move_to([0, self.sub_y, 0])
                m.actual = clave
        sub.add_updater(paso)
        return sub

    # ----- Ritmo -----
    def hasta(self, t_abs):
        """Espera hasta el instante absoluto t_abs. Si ya pasó, avisa: la animación se comió tiempo del beat."""
        self.t = self.renderer.time
        falta = t_abs - self.t
        if falta > 2 / config.frame_rate:
            self._foto()                 # lo que queda quieto en pantalla es lo que el espectador lee
        if self._tramo is not None:
            self._ventana()
            for limite in self._tramo:   # una espera que cruza el límite del tramo se parte ahí
                if self.t + 1 / config.frame_rate < limite < t_abs - 1 / config.frame_rate:
                    self.wait(limite - self.t)
                    self.t = self.renderer.time
                    self._ventana()
            falta = t_abs - self.t
        if falta > 1 / config.frame_rate:
            self.wait(falta)
        elif falta < -0.15:
            self._retrasos.append(dict(beat=self._beat_actual(), t=float(t_abs), retraso=float(-falta)))
            print(f"[AVISO] vas {-falta:.2f} s tarde respecto a t={t_abs:.2f}")

    def fin_beat(self, bid):
        self.hasta(self.g[bid]["fin"])
        self._foto()
        if self._rotulo is not None and self._rotulo_hasta == bid:
            self.remove(self._rotulo)
            self._rotulo, self._rotulo_hasta = None, None

    # ----- Transiciones reutilizables (Guía 2 §2) -----
    _SIN_CAMBIO = object()

    def enfocar_anim(self, *objetos, opacidad=0.93, ambiente=_SIN_CAMBIO, **kw):
        """Animación de «todo se difumina salvo estos objetos»: un velo del color del fondo cubre la escena y los
        objetos indicados quedan delante, intactos. Para combinarla con otras en un self.play. Ver enfocar().
        `ambiente`: el sonido de fondo del escenario aparte, en el mismo instante que la imagen:
        None lo corta, "laboratorio" lo cambia; sin el argumento, el sonido no cambia."""
        if getattr(self, "_velo", None) is None:
            self._velo = Rectangle(width=9.4, height=16.4, stroke_width=0, fill_color=FONDO, fill_opacity=0)
        self.add(self._velo, *objetos)                # el velo encima de todo; los objetos enfocados, encima del velo
        anim = self._velo.animate(**kw).set_fill(opacity=opacidad).build()
        if ambiente is not EscenaEstudio._SIN_CAMBIO:
            anim.ambiente_motor = ambiente
        return anim

    def enfocar(self, *objetos, opacidad=0.93, run_time=0.6, ambiente=_SIN_CAMBIO):
        """Todo se difumina y oscurece salvo `objetos`. Lo que se añada después queda delante del velo:
        sirve como «escenario aparte» sin cambiar de página. Se deshace con desenfocar()."""
        self.play(self.enfocar_anim(*objetos, opacidad=opacidad, ambiente=ambiente), run_time=run_time)

    def desenfocar_anim(self, ambiente=_SIN_CAMBIO, **kw):
        """Animación de vuelta: el velo se disuelve y la escena reaparece. El velo se retira solo al terminar.
        `ambiente="aire"` reanuda el sonido del escenario justo cuando reaparece."""
        velo, self._velo = self._velo, None
        anim = FadeOut(velo, **kw)
        if ambiente is not EscenaEstudio._SIN_CAMBIO:
            anim.ambiente_motor = ambiente
        return anim

    def desenfocar(self, run_time=0.8, ambiente=_SIN_CAMBIO):
        if getattr(self, "_velo", None) is not None:
            self.play(self.desenfocar_anim(ambiente=ambiente), run_time=run_time)

    def acercar(self, objetivo, factor=2.4, quitar=(), poner=(), sub_y=None, hacer=None, dur=0.5, fundido=0.22):
        """Transición «la cámara se acerca a un objeto»: la imagen actual se congela un instante y se amplía hacia
        `objetivo` (un objeto o un punto); al llegar, se cambia la escena (`quitar`, `poner`, `hacer`, como en
        pagina()) y la imagen ampliada se funde. El título, la barra y los subtítulos no se mueven.
        Úsala para pasar de un plano general a un detalle; para volver, pagina() o desenfocar()."""
        self.sonido("entrada")
        p = objetivo.get_center() if isinstance(objetivo, Mobject) else np.array([objetivo[0], objetivo[1], 0.0])
        hud = {id(m) for h in self._hud for m in h.get_family()}
        visibles = [m for m in self.mobjects if id(m) not in hud]
        self.camera.reset()
        self.camera.capture_mobjects(visibles)
        foto = ImageMobject(self.camera.pixel_array.copy())
        foto.height = config.frame_height
        foto.move_to(ORIGIN)
        self.add(foto)
        self.play(foto.animate.scale(factor, about_point=p).shift(-p * 0.85), run_time=dur, rate_func=rate_functions.ease_in_out_sine)
        if hacer:
            hacer()
        self.remove(*quitar)
        if self._rotulo is not None:
            self.remove(self._rotulo)
            self._rotulo, self._rotulo_hasta = None, None
        self.add(*poner)
        self.add(foto)
        if sub_y is not None:
            self.sub_y = sub_y
        self.play(foto.animate.set_opacity(0), run_time=fundido)
        self.remove(foto)

    def pagina(self, quitar=(), poner=(), sub_y=None, hacer=None, dur=0.24):
        """Cambio de escenario: una hoja pasa por delante; al taparlo todo se cambian los elementos.
        `hacer` es una función que se ejecuta justo cuando la hoja tapa la pantalla (cambios de pose,
        de temperatura, etc.). No hagas esos cambios antes de llamar a pagina(): se verían el salto."""
        self.sonido("pagina")
        hoja = Rectangle(width=9.4, height=16.4, fill_color=PAGINA, fill_opacity=1, stroke_color=TIZA, stroke_width=4).move_to([9.5, 0, 0])
        self.add(hoja)
        self.play(hoja.animate.move_to(ORIGIN), run_time=dur / 2, rate_func=rate_functions.ease_in_quad)
        if hacer:
            hacer()
        self.remove(*quitar)
        if self._rotulo is not None:          # el rótulo pertenece a la página que se va
            self.remove(self._rotulo)
            self._rotulo, self._rotulo_hasta = None, None
        self.add(*poner)
        self.add(hoja)
        if sub_y is not None:
            self.sub_y = sub_y
        self.play(hoja.animate.move_to([-9.5, 0, 0]), run_time=dur / 2, rate_func=rate_functions.ease_out_quad)
        self.remove(hoja)
