"""Revisión automática de la composición: solapes, zonas tapadas, textos pequeños y exceso de texto.

No mira píxeles: pregunta a la escena qué objetos importantes hay en pantalla y dónde están. Por eso funciona
también sin renderizar (producir.py --choques) y tarda segundos.

Qué es «importante»: todo texto o fórmula (Text, MathTex, números), todo personaje (clase Personaje) y el subtítulo
activo. Un objeto no cuenta si está aparcado fuera de cuadro o si su VISIBILIDAD EFECTIVA es menor que 0,25:
opacidad propia × producto de (1 − opacidad) de cada rectángulo que lo cubre por completo y se dibuja después
(un velo, el marco de una vista). El orden de dibujo es el de la cámara: z_index primero y, a igual z_index, el orden
de la escena.

CONTEO POR BLOQUES DE LECTURA (Guía 2 §7): un Text, un MathTex o un número suelto es un bloque; un grupo con el
atributo lectura="nombre" es UN bloque con todo lo que contiene; una píldora y el rótulo son un bloque cada uno; un
número que cambia de valor sigue siendo el mismo bloque. Máximo 8 bloques a la vez (sin título ni subtítulos) y
2 bloques nuevos por beat (un relevo de rótulo cuenta como uno nuevo).

PERTENENCIA: un marco o una píldora no «choca» con lo que vive dentro de él. Eso se decide por la cadena de
ancestros, no por la geometría: hay excepción si uno es ancestro del otro, o si los dos cuelgan de un mismo grupo
marcado con contenedor=True (personaje dentro de escenario).

EscenaEstudio toma una «foto» de la composición cada vez que la escena se queda quieta (hasta(), fin_beat()), que es
lo que el espectador llega a leer, y al terminar escribe revision/choques.json. producir.py lo pasa al informe.
"""
import json
import os

import numpy as np
from manim import *

TAM_MIN = 20            # tamaño de letra mínimo (font_size de Manim) para leerse en un teléfono
MAX_TEXTOS = 8          # bloques de lectura a la vez en pantalla, sin contar título ni subtítulos
MAX_NUEVOS = 2          # bloques de lectura nuevos por beat
VISIBLE = 0.25          # visibilidad efectiva mínima para que un objeto cuente
SOLAPE_TEXTO = 0.08     # fracción del texto más pequeño que puede pisar otro texto
SOLAPE_PERSONAJE = 0.15  # fracción de un texto que puede quedar sobre un personaje
GLIFOS_DUDOSOS = "₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹·"  # la fuente del canal no los tiene (salen como un cuadro): usar MathTex u otro signo
_TEXTOS = (Text, MarkupText, MathTex, Tex, DecimalNumber)


def _caja(mob):
    izq, der, aba, arr = mob.get_left()[0], mob.get_right()[0], mob.get_bottom()[1], mob.get_top()[1]
    return [float(izq), float(aba), float(der), float(arr)]


def _area(c):
    return max(0.0, c[2] - c[0]) * max(0.0, c[3] - c[1])


def _cruce(a, b):
    return _area([max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])])


def _dentro(a, b, tol=0.03):
    """¿La caja a está entera dentro de b?"""
    return a[0] >= b[0] - tol and a[1] >= b[1] - tol and a[2] <= b[2] + tol and a[3] <= b[3] + tol


def _opacidad(mob):
    piezas = mob.family_members_with_points()
    return max((max(p.get_fill_opacity(), p.get_stroke_opacity()) for p in piezas), default=0.0)


def _toca_cuadro(caja, mob, escena, zoom=1.0):
    """Descarta lo totalmente aparcado; conserva cualquier recorte visible, incluido el trazo."""
    camara = getattr(escena, "camera", None)
    ancho = float(getattr(camara, "frame_width", config.frame_width))
    alto = float(getattr(camara, "frame_height", config.frame_height))
    k = float(getattr(camara, "cairo_line_width_multiple", 0.01))
    trazo = 0.0
    for p in mob.family_members_with_points():
        if isinstance(p, VMobject):
            for fondo in (False, True):
                if p.get_stroke_opacity(background=fondo) > 0:
                    trazo = max(trazo, p.get_stroke_width(background=fondo))
    margen = trazo * k * zoom
    return not (caja[2] + margen < -ancho / 2 or caja[0] - margen > ancho / 2 or
                caja[3] + margen < -alto / 2 or caja[1] - margen > alto / 2)


def _nombre(mob):
    if isinstance(mob, DecimalNumber):
        return "un contador"
    texto = getattr(mob, "original_text", None) or getattr(mob, "text", None) or getattr(mob, "tex_string", None) or type(mob).__name__
    texto = " ".join(str(texto).split())
    return "«" + (texto if len(texto) <= 34 else texto[:33] + "…") + "»"


def recoger(escena):
    """Lista de objetos importantes visibles, en orden de dibujo. Cada uno es un dict con: tipo, nombre, caja, tam,
    hud, orden (z_index, orden en la escena), texto, id, anc (ids de sus ancestros), cont (ids de los ancestros
    marcados contenedor), vis (visibilidad efectiva) y bloque (clave, nombre y objeto de su bloque de lectura)."""
    hud = {id(m) for h in getattr(escena, "_hud", ()) for m in h.get_family()}
    objetos, tapas, n = [], [], [0]
    # Encuadre (acercamiento de cámara): todo lo que no es HUD ni `.fijo` se mide en coordenadas de PANTALLA
    z, c = escena.estado_camara() if hasattr(escena, "estado_camara") else (1.0, None)

    def pantalla(caja, fijo):
        if fijo or c is None or abs(z - 1) < 1e-6:
            return caja
        return [(caja[0] - c[0]) * z, (caja[1] - c[1]) * z, (caja[2] - c[0]) * z, (caja[3] - c[1]) * z]

    def visitar(m, anc, cont, bloque, fijo=False, inserto=False):
        if getattr(m, "no_revisar", False):
            return
        fijo = fijo or getattr(m, "fijo", False) or id(m) in hud
        inserto = inserto or getattr(m, "inserto", False)
        n[0] += 1
        orden = (getattr(m, "z_index", 0), n[0])
        lectura = getattr(m, "lectura", None)
        if lectura and bloque is None:
            bloque = (id(m), f"«{lectura}»", m)
        es_personaje = hasattr(m, "POSES") and hasattr(m, "refrescar")
        if isinstance(m, _TEXTOS) or es_personaje:
            if not m.family_members_with_points():
                return
            op = _opacidad(m)
            if op < VISIBLE:
                return
            caja = pantalla(m.caja_cuerpo() if es_personaje and hasattr(m, "caja_cuerpo") else _caja(m), fijo)
            if _area(caja) <= 0 or not _toca_cuadro(caja, m, escena, 1.0 if fijo else z):
                return
            tam = None
            if not es_personaje:
                try:
                    tam = float(m.font_size)
                except Exception:
                    tam = None
            nombre = type(m).__name__ if es_personaje else _nombre(m)
            objetos.append(dict(tipo="personaje" if es_personaje else "texto", nombre=nombre, caja=caja, tam=tam,
                                hud=id(m) in hud, orden=orden, texto=str(getattr(m, "text", "")), id=id(m), anc=anc,
                                cont=cont, vis=op, bloque=None if es_personaje else (bloque or (id(m), nombre, m)),
                                inserto=inserto))
            if es_personaje and hasattr(m, "cajas_colision"):
                objetos[-1]["partes"] = [pantalla(p, fijo) for p in m.cajas_colision()]
            elif not es_personaje:
                piezas = m.family_members_with_points()
                pintada = next((p for p in piezas if p.get_fill_opacity() >= VISIBLE), piezas[0])
                # Los arrays efectivos siguen siendo RGBA durante Write y en estilos multicolor;
                # el atributo background_stroke_color, en cambio, puede ser una lista.
                ancho = float(pintada.get_stroke_width(background=True))
                opacidad = float(pintada.get_stroke_opacity(background=True))
                objetos[-1].update(color=(pintada.get_fill_rgbas()[0, :3]*255).tolist(),
                                   contorno_ancho=ancho, contorno_opacidad=opacidad)
                if ancho > 0 and opacidad > 0:
                    objetos[-1]["contorno_color"] = (pintada.get_stroke_rgbas(background=True)[0, :3]*255).tolist()
            return
        if getattr(m, "importante", False) and m.family_members_with_points():          # marcos y píldoras
            op = _opacidad(m)
            if op >= VISIBLE and _toca_cuadro(pantalla(_caja(m), fijo), m, escena, 1.0 if fijo else z):
                objetos.append(dict(tipo="objeto", nombre=getattr(m, "nombre", type(m).__name__), caja=pantalla(_caja(m), fijo), tam=None,
                                    hud=False, orden=orden, texto="", id=id(m), anc=anc, cont=cont, vis=op, bloque=None))
        if isinstance(m, Rectangle) and len(m.points) and m.get_fill_opacity() > 0:
            tapas.append(dict(orden=orden, caja=pantalla(_caja(m), fijo), op=float(m.get_fill_opacity()), id=id(m), anc=set(anc)))
        hijos_anc = anc + (id(m),)
        hijos_cont = cont + ((id(m),) if getattr(m, "contenedor", False) else ())
        for s in m.submobjects:
            visitar(s, hijos_anc, hijos_cont, bloque, fijo, inserto)

    for m in escena.mobjects:
        visitar(m, (), (), None)
    # visibilidad efectiva: cada rectángulo que lo cubre entero y se dibuja después deja pasar (1 - opacidad)
    visibles = []
    for o in objetos:
        for t in tapas:
            if t["orden"] > o["orden"] and t["id"] != o["id"] and o["id"] not in t["anc"] and t["id"] not in o["anc"] \
                    and _dentro(o["caja"], t["caja"]):
                o["vis"] *= 1.0 - t["op"]
        if o["vis"] >= VISIBLE:
            visibles.append(o)
    return visibles


def _relacionados(a, b):
    """¿Uno vive dentro del otro? Solo por pertenencia: ancestro directo, o hermanos dentro de un contenedor."""
    if a.get("id") is None or b.get("id") is None:
        return False
    if a["id"] in b.get("anc", ()) or b["id"] in a.get("anc", ()):
        return True
    return bool(set(a.get("cont", ())) & set(b.get("cont", ())))


def _bloque(o):
    return o.get("bloque") or (o.get("id", id(o)), o["nombre"], None)


def bloques(objetos):
    """Bloques de lectura visibles (sin título ni subtítulos): {clave: (nombre, objeto, caja)}."""
    res = {}
    for o in objetos:
        if o["tipo"] != "texto" or o["hud"]:
            continue
        clave, nombre, ref = _bloque(o)
        if clave in res:
            c = res[clave][2]
            res[clave] = (nombre, ref, [min(c[0], o["caja"][0]), min(c[1], o["caja"][1]), max(c[2], o["caja"][2]), max(c[3], o["caja"][3])])
        else:
            res[clave] = (nombre, ref, list(o["caja"]))
    return res


def _area_union(cajas):
    xs = sorted({x for c in cajas for x in (c[0], c[2])})
    total = 0.0
    for a, b in zip(xs, xs[1:]):
        tramos = sorted((c[1], c[3]) for c in cajas if c[0] < b and c[2] > a)
        fin, alto = -float("inf"), 0.0
        for lo, hi in tramos:
            alto += max(0, hi-max(lo, fin))
            fin = max(fin, hi)
        total += (b-a)*alto
    return total


def _cruce_personaje(texto, personaje):
    a = texto["caja"]
    cajas = [[max(a[0],b[0]), max(a[1],b[1]), min(a[2],b[2]), min(a[3],b[3])]
             for b in personaje.get("partes", [personaje["caja"]]) if _cruce(a,b) > 0]
    return _area_union(cajas)


def revisar(objetos, y_min=-4.8, x_max=3.15, perfil=None):
    """Devuelve los hallazgos de una foto: lista de dict(tipo, clave, texto, caja)."""
    h = []

    def une(a, b):
        return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]

    for i, a in enumerate(objetos):
        for b in objetos[i + 1:]:
            if a["hud"] and b["hud"]:
                continue
            tipos = {a["tipo"], b["tipo"]}
            if tipos == {"texto", "personaje"}:
                t, p = (a, b) if a["tipo"] == "texto" else (b, a)
                cruce = _cruce_personaje(t, p)
            else:
                cruce = _cruce(a["caja"], b["caja"])
            if cruce <= 0:
                continue
            tipos = {a["tipo"], b["tipo"]}
            if "objeto" in tipos:      # un marco o una píldora: choca si pisa algo que no vive dentro de él
                if not _relacionados(a, b) and cruce / min(_area(a["caja"]), _area(b["caja"])) > SOLAPE_TEXTO:
                    h.append(dict(tipo="solape", clave=("solape", a["nombre"], b["nombre"]), caja=une(a["caja"], b["caja"]),
                                  texto=f"{a['nombre']} y {b['nombre']} se pisan"))
            elif tipos == {"texto"}:
                if _bloque(a)[0] == _bloque(b)[0]:      # partes de un mismo bloque de lectura (los ejes, el indicador)
                    continue
                if cruce / min(_area(a["caja"]), _area(b["caja"])) > SOLAPE_TEXTO:
                    h.append(dict(tipo="solape", clave=("solape", a["nombre"], b["nombre"]), caja=une(a["caja"], b["caja"]),
                                  texto=f"{a['nombre']} y {b['nombre']} se pisan"))
            elif tipos == {"texto", "personaje"}:
                t, p = (a, b) if a["tipo"] == "texto" else (b, a)
                if t.get("inserto"):   # inserto (`.inserto = True`): va encima del personaje a propósito; se cuenta todo lo demás
                    continue
                if cruce / _area(t["caja"]) > SOLAPE_PERSONAJE:
                    h.append(dict(tipo="personaje", clave=("personaje", t["nombre"], p["nombre"]), caja=une(a["caja"], b["caja"]),
                                  texto=f"{t['nombre']} queda sobre {p['nombre']} (o {p['nombre']} lo tapa)"))
    if perfil:
        from zonas import contiene, normalizar
        for o in objetos:
            if not contiene(normalizar(o["caja"]), perfil, tolerancia=0.002):
                h.append(dict(tipo="zona", clave=("perfil", perfil, o["nombre"]), caja=o["caja"],
                              texto=f"{o['nombre']} sale del perfil de revisión {perfil} (ver su fuente y alcance)"))
    visibles = [o for o in objetos if not o["hud"]]
    for o in visibles:
        c = o["caja"]
        if c[1] < y_min - 0.05 or c[2] > x_max + 0.05:
            donde = "abajo (y < %.1f)" % y_min if c[1] < y_min - 0.05 else "a la derecha (x > %.2f)" % x_max
            h.append(dict(tipo="zona", clave=("zona", o["nombre"]), caja=c, texto=f"{o['nombre']} entra en la zona que tapan las plataformas, {donde}"))
        if c[0] < -4.5 or c[3] > 8.0:
            h.append(dict(tipo="fuera", clave=("fuera", o["nombre"]), caja=c, texto=f"{o['nombre']} se sale del cuadro"))
        if o["tipo"] == "texto":
            if o["tam"] is not None and o["tam"] < TAM_MIN - 0.5:
                h.append(dict(tipo="pequeno", clave=("pequeno", o["nombre"]), caja=c,
                              texto=f"{o['nombre']} es demasiado pequeño para un teléfono (tamaño {o['tam']:.0f}, mínimo {TAM_MIN})"))
            if any(ch in GLIFOS_DUDOSOS for ch in o["texto"]):
                h.append(dict(tipo="glifo", clave=("glifo", o["nombre"]), caja=c,
                              texto=f"{o['nombre']} usa un carácter que la fuente no tiene (subíndice, superíndice o «·»; saldrá como un cuadro): usa MathTex u otro signo"))
    n = len(bloques(objetos))
    if n > MAX_TEXTOS:
        h.append(dict(tipo="exceso", clave=("exceso",), caja=[-4.4, -4.7, 3.1, 6.2], n=n,
                      texto=f"hay {n} textos a la vez (máximo {MAX_TEXTOS} bloques de lectura, sin contar título ni subtítulos)"))
    return h


class Registro:
    """Acumula los hallazgos de todas las fotos de una escena, sin repetir el mismo problema.
    También cuenta los bloques de lectura NUEVOS de cada beat: los que aparecen respecto a los que había al terminar
    el beat anterior (lo que aparece en la pausa entre dos beats se atribuye al siguiente). Guarda una referencia a
    cada bloque para que su identidad no se confunda con la de un objeto nuevo."""

    def __init__(self):
        self.fotos, self.vistos, self.inicio_tramo = 0, {}, 0.0
        self.muestras, self.max_bloques, self.nuevos_por_beat = [], 0, {}
        # _base: bloques al terminar el beat anterior · _fin: los de la última foto del beat actual
        # _nuevos: bloques aparecidos en el beat actual · _pausa: aparecidos entre beats (van al siguiente)
        self._beat, self._base, self._fin, self._nuevos, self._pausa = None, {}, {}, {}, {}

    def _contar_nuevos(self, objetos, beat):
        actuales = bloques(objetos)
        if beat is None:
            for k, v in actuales.items():
                if k not in self._fin:
                    self._pausa.setdefault(k, v)
            return []
        if beat != self._beat:
            self._beat, self._base, self._nuevos = beat, self._fin, dict(self._pausa)
        self._pausa = {}
        for k, v in actuales.items():
            if k not in self._base:
                self._nuevos.setdefault(k, v)
        self._fin = actuales
        if len(self._nuevos) <= MAX_NUEVOS:
            return []
        nombres = [v[0] for v in self._nuevos.values()]
        cajas = [v[2] for v in self._nuevos.values()]
        caja = [min(c[0] for c in cajas), min(c[1] for c in cajas), max(c[2] for c in cajas), max(c[3] for c in cajas)]
        return [dict(tipo="nuevos", clave=("nuevos", beat), caja=caja, n=len(nombres),
                     texto=f"en {beat} aparecen {len(nombres)} textos nuevos (máximo {MAX_NUEVOS}): " + ", ".join(nombres))]

    def foto(self, escena, beat, y_min=-4.8, x_max=3.15):
        self.fotos += 1
        objetos = recoger(escena)
        nuevos = self._contar_nuevos(objetos, beat)
        self.max_bloques = max(self.max_bloques, len(bloques(objetos)))
        if beat:
            self.nuevos_por_beat[beat] = max(self.nuevos_por_beat.get(beat, 0), len(self._nuevos))
        campos = ("tipo", "nombre", "caja", "tam", "vis", "color", "contorno_color", "contorno_ancho", "contorno_opacidad", "hud")
        self.muestras.append(dict(t=round(float(escena.t), 4), beat=beat,
                                  objetos=[{k:o[k] for k in campos if k in o} for o in objetos]))
        for h in revisar(objetos, y_min, x_max, os.environ.get("PERFIL_ZONA") or None) + nuevos:
            v = self.vistos.setdefault(h["clave"], dict(tipo=h["tipo"], texto=h["texto"], t=round(float(escena.t), 2), beats=[], cajas={}, veces=0, max=0))
            v["veces"] += 1
            if h["tipo"] in ("exceso", "nuevos"):     # se queda con el peor momento
                if h["n"] > v["max"]:
                    v["max"], v["texto"] = h["n"], h["texto"]
                    if h["tipo"] == "exceso":
                        v["t"] = round(float(escena.t), 2)
            if beat and beat not in v["beats"]:
                v["beats"].append(beat)
            if beat:
                v["cajas"][beat] = [round(x, 3) for x in h["caja"]]

    def guardar(self, ruta):
        orden = {"solape": 0, "personaje": 1, "zona": 2, "fuera": 3, "glifo": 4, "pequeno": 5, "exceso": 6, "nuevos": 7}
        lista = sorted(self.vistos.values(), key=lambda v: (orden.get(v["tipo"], 9), v["t"]))
        for v in lista:
            v.pop("max", None)
        ruta.parent.mkdir(exist_ok=True)
        ruta.write_text(json.dumps(dict(fotos=self.fotos, inicio_tramo=round(self.inicio_tramo, 3), hallazgos=lista,
                                       max_bloques=self.max_bloques, nuevos_por_beat=self.nuevos_por_beat,
                                       muestras=self.muestras), ensure_ascii=False, indent=1), encoding="utf-8")
        return lista


ETIQUETA = {"solape": "Textos que se pisan", "personaje": "Personaje y texto encimados", "zona": "Zona tapada por las plataformas",
            "fuera": "Fuera de cuadro", "glifo": "Caracteres que la fuente no tiene", "pequeno": "Texto demasiado pequeño",
            "exceso": "Demasiado texto a la vez", "nuevos": "Demasiados textos nuevos en un beat"}


def resumen(hallazgos):
    """Líneas de texto para el informe, agrupadas por tipo."""
    lineas = []
    for tipo, titulo in ETIQUETA.items():
        grupo = [v for v in hallazgos if v["tipo"] == tipo]
        if grupo:
            lineas.append(f"**{titulo} ({len(grupo)})**")
            for v in grupo:
                beats = ", ".join(v["beats"]) if v["beats"] else "—"
                lineas.append(f"- {v['texto']} · {beats} · desde el segundo {v['t']:.1f}")
    return lineas
