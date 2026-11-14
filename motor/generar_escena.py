"""Borrador revisable de escena desde guion.json. Nunca sobrescribe una escena ni genera voces.

Además del esqueleto por beat, convierte en código las **acciones** declaradas en el guion y
crea los **objetos** del episodio con las recetas de actuación del motor (piezas/objetos.py). Lo que no está declarado
queda como sugerencia comentada, deducida del campo `visual`. El borrador sigue protegido con `pendiente_animar`.

Guion (campos opcionales):
    "objetos": {"taza2": {"tipo": "TazaVacia", "pos": [-0.15, -3.86], "escala": 0.6, "importante": true,
                          "tocado": true},
                "nota_a": {"tipo": "NotaMesa", "pos": [0.72, -3.48], "giro": -6}}
    beat "acciones": [{"palabra": "Sí", "hace": "empujar", "objeto": "taza2", "hasta": [-0.62, -3.88]},
                      {"palabra": "frío", "hace": "tocar", "punto": [2.35, -3.66]},
                      {"palabra": "La", "hace": "leer_nota", "texto": "Pieza lista", "girar": "lista"}]
Vocabulario de `hace`: ver ACCIONES.
"""
import ast
import json
import re
from pathlib import Path

# hace → (parámetros obligatorios, descripción)
ACCIONES = {
    "pose": (("pose",), "personaje.anim(pose=…)"),
    "expresion": (("expresion",), "personaje.anim(expresion=…)"),
    "mirar": (("gesto",), "personaje.anim(gesto=(giro, mirada x, mirada y, ceja))"),
    "tocar": ((), "la mano a un `punto` [x, y] o al borde de un `objeto`"),
    "empujar": (("objeto", "hasta"), "mano y objeto juntos hasta [x, y]"),
    "rotulo": (("texto",), "rótulo de una sola aclaración hasta el final del beat"),
    "leer_nota": (("texto",), "inserto con nota que se gira (en `girar`) y vuelve boca abajo al final del beat"),
    "leer": ((), "personaje: lee su cuaderno"),
    "escuchar": ((), "personaje: escucha"),
    "detener_lapiz": ((), "personaje: detiene el lápiz"),
    "tachar": ((), "personaje: el tachón que queda"),
}
TIPOS_OBJETO = {"TazaVacia": ("pos",), "NotaMesa": ("pos",)}

# Sugerencias para beats sin acciones: palabra del `visual` → receta del motor
PISTAS = [
    (r"\b(empuj|desliz|apart|llev|acerc|traslad)", "empujar(personaje, <objeto>, <destino>)  (piezas/objetos.py)"),
    (r"\b(gir\w* .*nota|nota .*gir|se lee|leer?)\b", "leer_nota: inserto con NotaGrande(texto).girar() y ManoInserto"),
    (r"\b(toca|roza|apoya)", "personaje.anim(**personaje.alcanzar(x, y))"),
    (r"\b(mira|mirada|levanta la vista|baja la vista)", "personaje.anim(gesto=(giro, mirada x, mirada y, ceja))"),
    (r"\b(r[oó]tulo)", "*self.rotulo_anim(TEXTO, hasta=bid)"),
    (r"\b(tach)", "personaje.tachar()"),
    (r"\b(inserto|primer plano)", "self.enfocar_anim(inserto, ambiente=None) … self.desenfocar_anim(ambiente=…)"),
]


def _num(v, n):
    return isinstance(v, list) and len(v) == n and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)


def _objetos(g, RECETAS):
    objs = g.get("objetos", {}) or {}
    lineas, por_receta = [], {}
    for nombre, o in objs.items():
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", nombre):
            raise ValueError(f"Objeto {nombre!r}: nombre en minúsculas, válido en Python.")
        tipo = o.get("tipo")
        if tipo not in TIPOS_OBJETO:
            raise ValueError(f"Objeto {nombre!r}: tipo {tipo!r} desconocido (válidos: {sorted(TIPOS_OBJETO)}).")
        if not _num(o.get("pos"), 2):
            raise ValueError(f"Objeto {nombre!r}: 'pos' debe ser [x, y].")
        x, y = o["pos"]
        if tipo == "TazaVacia":
            lineas.append(f"        {nombre} = TazaVacia(({x}, {y}), {float(o.get('escala', 1.0))})")
        else:
            lineas.append(f"        {nombre} = NotaMesa({x}, {y}, {float(o.get('giro', 0))})")
        if o.get("importante"):
            lineas.append(f"        {nombre}.importante = True")
        receta = o.get("receta", g.get("receta"))
        if receta not in RECETAS:
            raise ValueError(f"Objeto {nombre!r}: necesita la receta donde vive (receta {receta!r} desconocida).")
        por_receta.setdefault(receta, []).append((nombre, bool(o.get("tocado"))))
    return objs, lineas, por_receta


def _accion(bid, a, palabras, objs, personaje, abierto=None):
    hace, palabra = a["hace"], a["palabra"]
    if hace not in ACCIONES:
        raise ValueError(f"{bid}: acción {hace!r} desconocida (válidas: {sorted(ACCIONES)}).")
    for k in ACCIONES[hace][0]:
        if k not in a:
            raise ValueError(f"{bid}: la acción {hace!r} necesita {k!r}.")
    if palabra.casefold() not in palabras:
        raise ValueError(f"{bid}: la palabra {palabra!r} de la acción {hace!r} no está en el texto.")
    if "objeto" in a and a["objeto"] not in objs:
        raise ValueError(f"{bid}: objeto {a['objeto']!r} no declarado en 'objetos'.")
    n, rt, antes = int(a.get("n", 0)), float(a.get("run_time", 0.45)), float(a.get("antes", 0.15))
    en = lambda *anims, rt=rt, p=palabra: f"        self.en({bid!r}, {p!r}, {', '.join(anims)}, n={n}, run_time={rt}, antes={antes})"
    if hace in ("pose", "expresion"):
        return [en(f"{personaje}.anim({hace}={a[hace]!r})")]
    if hace == "mirar":
        if not _num(a["gesto"], 4):
            raise ValueError(f"{bid}: 'gesto' debe ser [giro, mirada x, mirada y, ceja].")
        return [en(f"{personaje}.anim(gesto={tuple(a['gesto'])!r})")]
    if hace == "tocar":
        if "objeto" in a:
            return [en(f"{personaje}.anim(**{personaje}.alcanzar(*{a['objeto']}.borde()))")]
        if not _num(a.get("punto"), 2):
            raise ValueError(f"{bid}: 'tocar' necesita 'objeto' o 'punto' [x, y].")
        return [en(f"{personaje}.anim(**{personaje}.alcanzar({a['punto'][0]}, {a['punto'][1]}))")]
    if hace == "empujar":
        if not _num(a["hasta"], 2):
            raise ValueError(f"{bid}: 'hasta' debe ser [x, y].")
        return [en(f"*empujar({personaje}, {a['objeto']}, ({a['hasta'][0]}, {a['hasta'][1]}))", rt=float(a.get("run_time", 0.8)))]
    if hace == "rotulo":
        return [en(f"*self.rotulo_anim({a['texto']!r}, hasta={bid!r})", rt=float(a.get("run_time", 0.3)))]
    if hace == "leer_nota":
        girar = a.get("girar", palabra)
        if girar.casefold() not in palabras:
            raise ValueError(f"{bid}: la palabra {girar!r} (girar) no está en el texto.")
        v = f"ins_{bid}"
        return [f"        {v}_nota = NotaGrande({a['texto']!r}).scale(0.8).move_to([0.9, -0.3, 0])",
                f"        {v}_mano = ManoInserto((2.35, -1.5))",
                f"        {v} = VGroup(RoundedRectangle(corner_radius=0.2, width=7.4, height=4.6, stroke_color=TIZA, stroke_width=5,",
                f"                     fill_color='#211E24', fill_opacity=1), {v}_nota, {v}_mano).move_to([0, 0.25, 0])",
                f"        {v}.inserto = True",
                (en(f"FadeOut({abierto})", f"FadeIn({v})", rt=0.4) if abierto else
                 en(f"self.enfocar_anim({v}, ambiente=None)", f"FadeIn({v})", rt=0.4)),
                f"        self.en({bid!r}, {girar!r}, {v}_nota.girar(0.55), run_time=0.55, antes=0.4)",
                f"        self.hasta(g[{bid!r}]['fin'] - 0.62)",
                f"        self.play({v}_nota.girar(0.5), run_time=0.5)"]
    return [en(f"{personaje}.{hace}()", rt=float(a.get("run_time", 0.5)))]


def crear(carpeta, destino=None):
    carpeta = Path(carpeta).resolve()
    destino = Path(destino).resolve() if destino else carpeta / "escena.py"
    if destino.parent != carpeta or destino.suffix != ".py":
        raise ValueError("El esqueleto debe ser un .py dentro de la carpeta del guion.")
    if destino.exists():
        raise FileExistsError(f"No se sobrescribe {destino}; conserva o renombra la escena existente.")
    g = json.loads((carpeta / "guion.json").read_text(encoding="utf-8"))
    beats = g.get("beats", [])
    if not beats:
        raise ValueError("El guion no tiene beats.")
    from plano import COMPOSICIONES
    from sonido import CATALOGO
    from recetas import RECETAS
    objs, cuerpo, por_receta = _objetos(g, RECETAS)
    ids, receta_actual, abierto = set(), None, None      # abierto: inserto en pantalla (velo puesto)
    for b in beats:
        bid = b["id"]
        if bid in ids:
            raise ValueError(f"Beat repetido: {bid}")
        ids.add(bid)
        receta = b.get("receta", g.get("receta"))
        comp = b.get("composicion")
        if receta and receta not in RECETAS:
            raise ValueError(f"{bid}: receta desconocida {receta!r}.")
        if not receta and comp not in COMPOSICIONES:
            raise ValueError(f"{bid}: composición desconocida {comp!r}.")
        palabras = re.findall(r"\w+", b["texto"].casefold())
        claves = list(b.get("claves", {}))
        for clave in claves:
            if clave.casefold() not in palabras:
                raise ValueError(f"{bid}: la clave {clave!r} no es una palabra del texto.")
        comentario = " ".join(str(b["texto"]).splitlines())
        cuerpo.append(f"        # {bid}: {comentario}")
        if receta:
            if receta != receta_actual:
                # self.montar(): corte a mitad de la pausa + receta (con ajustes_receta del guion) + objetos fijos
                args = [repr(receta)]
                if receta in por_receta:
                    args += [n for n, t in por_receta[receta] if not t]
                    toc = ", ".join(n for n, t in por_receta[receta] if t)
                    if toc:
                        args.append(f"tocados=({toc},)")
                cuerpo += [f"        montaje = self.montar({', '.join(args)})", "        personaje = montaje.personaje"]
                receta_actual = receta
        else:
            receta_actual = None
            cuerpo += [f"        self.plano = Plano({comp!r})", "        self.sub_y = self.plano.sub_y"]
        # El escenario se monta ANTES de esperar al beat: así el primer subtítulo ya nace en su sitio y el corte de
        # escenario cae en la pausa entre beats (como en las escenas hechas a mano).
        cuerpo.append(f"        self.hasta(g[{bid!r}]['ini'])")
        if "ambiente" in b:
            amb = b["ambiente"]
            if amb is not None and (amb not in CATALOGO or CATALOGO[amb][1] != "ambiente"):
                raise ValueError(f"{bid}: ambiente desconocido {amb!r}.")
            cuerpo.append(f"        self.ambiente({amb!r})")
        visual = str(b.get("visual", ""))
        cuerpo += ["        # Visual: " + linea for linea in visual.splitlines()]
        acciones = b.get("acciones") or []
        if abierto and not any(a.get("hace") == "leer_nota" for a in acciones[:1]):
            amb = RECETAS[receta_actual]["ambiente"] if receta_actual else None
            cuerpo += [f"        self.play(self.desenfocar_anim(ambiente={amb!r}), FadeOut({abierto}), run_time=0.45)",
                       f"        self.remove({abierto})"]
            abierto = None
        if acciones:
            for a in acciones:
                cuerpo += _accion(bid, a, palabras, objs, "personaje", abierto)
                if a.get("hace") == "leer_nota":
                    abierto = f"ins_{bid}"
            cuerpo.append("        # Revisar: miradas, tiempos y lo que el visual pida además de estas acciones.")
        else:
            sugeridas = [r for patron, r in PISTAS if re.search(patron, visual, re.I)]
            cuerpo += [f"        # Sugerencia: {r}" for r in sugeridas]
            cuerpo.append("        # TODO: sustituir las esperas por movimientos y objetos de la explicación.")
            for clave in claves:
                cuerpo.append(f"        self.en({bid!r}, {clave!r}, Wait(0.1), n=0, run_time=0.1, antes=0)")
                if palabras.count(clave.casefold()) > 1:
                    cuerpo.append(f"        # {clave!r} se repite: n=0 selecciona la primera aparición; revisar la intención.")
        cuerpo += [f"        self.fin_beat({bid!r})", ""]
    if abierto:                                   # el último beat acaba dentro de un inserto: se cierra antes del final
        amb = RECETAS[receta_actual]["ambiente"] if receta_actual else None
        cuerpo[-2:-2] = [f"        self.hasta(g[{bid!r}]['fin'] - 0.5)",
                         f"        self.play(self.desenfocar_anim(ambiente={amb!r}), FadeOut({abierto}), run_time=0.45)"]
    fuente = '''"""BORRADOR generado: completar y revisar las animaciones antes de producir."""
import sys
from pathlib import Path
AQUI = Path(__file__).resolve().parent
RAIZ = next(p for p in AQUI.parents if (p / "motor" / "estudio.py").exists())
sys.path.insert(0, str(RAIZ / "motor"))
from estudio import *
from recetas import objetos_en_mesa


class EscenaGenerada(EscenaEstudio):
    carpeta = AQUI
    pendiente_animar = True

    def construct(self):
        if self.pendiente_animar:
            raise NotImplementedError("Completa las animaciones y revisa el visual antes de quitar pendiente_animar.")
        g = self.g
'''+"\n".join(cuerpo)
    ast.parse(fuente)
    with destino.open("x", encoding="utf-8", newline="\n") as f:
        f.write(fuente)
    return destino
