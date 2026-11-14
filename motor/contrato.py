"""Contrato compartido de guion, voces y tiempos. No importa Manim ni servicios externos."""
import math
import re

from configuracion import CONFIG

VOCES = dict(CONFIG.get("voces", {}))
PROSODIA = {k: tuple(v) for k, v in CONFIG.get("prosodia", {}).items()}
CAMPOS_BEAT = {"id", "personaje", "escenario", "texto", "visual", "claves", "cola", "rate", "pitch", "voz",
               "afirmacion", "fuente", "composicion", "ambiente", "receta", "acciones"}
FORMATOS = {k: tuple(v) for k, v in CONFIG.get("formatos", {"largo": (0, float("inf"))}).items()}
PAUSA_ENTRE_BEATS = 0.34


def numero(n):
    return isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n)


def estructura(g, completo=True):
    if not isinstance(g, dict):
        return ["El guion debe ser un objeto JSON, no una lista ni un valor suelto"]
    e = []
    if completo:
        for k in ("id", "titulo", "curso", "especialista", "concepto"):
            if not isinstance(g.get(k), str) or not g[k].strip():
                e.append(f"'{k}' debe ser texto no vacío")
        for k in ("formato", "estado", "ficha", "verificacion", "perfil_editorial", "receta"):
            if k in g and not isinstance(g[k], str):
                e.append(f"'{k}' debe ser texto")
        if "pruebas" in g and not isinstance(g["pruebas"], dict):
            e.append("'pruebas' debe ser un objeto")
        if "sonido" in g and not isinstance(g["sonido"], bool):
            e.append("'sonido' debe ser true o false")
        if "dependencias" in g and (not isinstance(g["dependencias"], list) or
                                     any(not isinstance(p, str) for p in g["dependencias"])):
            e.append("'dependencias' debe ser una lista de rutas")
    if "objetos" in g and (not isinstance(g["objetos"], dict) or
                           any(not isinstance(v, dict) or not isinstance(v.get("tipo"), str) for v in g["objetos"].values())):
        e.append("'objetos' debe ser un objeto {nombre: {tipo, pos, …}}")
    if not isinstance(g.get("beats"), list) or not g["beats"]:
        return e + ["'beats' debe ser una lista no vacía"]
    vistos = set()
    for i, b in enumerate(g["beats"], 1):
        if not isinstance(b, dict):
            e.append(f"beat {i}: debe ser un objeto")
            continue
        bid = b.get("id", f"beat {i}")
        for k in (("id", "personaje", "texto", "escenario", "visual") if completo else ("id", "personaje", "texto")):
            if not isinstance(b.get(k), str) or not b[k].strip():
                e.append(f"{bid}: '{k}' debe ser texto no vacío")
        if isinstance(b.get("personaje"), str) and b["personaje"] not in VOCES and not b.get("voz"):
            e.append(f"{bid}: el personaje '{b['personaje']}' no tiene voz asignada")
        if not isinstance(bid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", bid):
            e.append(f"beat {i}: id inválido para nombre de archivo")
        elif bid in vistos:
            e.append(f"{bid}: id repetido")
        else:
            vistos.add(bid)
        if "cola" in b and (not numero(b["cola"]) or b["cola"] < 0):
            e.append(f"{bid}: cola debe ser un número finito no negativo")
        if "claves" in b and (not isinstance(b["claves"], dict) or
                             any(not isinstance(k, str) or not isinstance(v, str) for k, v in b["claves"].items())):
            e.append(f"{bid}: claves debe ser un objeto de palabras y colores")
        if "acciones" in b and (not isinstance(b["acciones"], list) or any(
                not isinstance(x, dict) or not isinstance(x.get("palabra"), str) or not isinstance(x.get("hace"), str)
                for x in b["acciones"])):
            e.append(f"{bid}: acciones debe ser una lista de {{palabra, hace, …}}")
        for k in ("voz", "rate", "pitch", "afirmacion", "fuente", "composicion", "ambiente", "receta"):
            if k in b and b[k] is not None and not isinstance(b[k], str):
                e.append(f"{bid}: '{k}' debe ser texto")
        for k, patron in (("rate", r"[+-]\d+%"), ("pitch", r"[+-]\d+Hz")):
            if k in b and (not isinstance(b[k], str) or not re.fullmatch(patron, b[k])):
                e.append(f"{bid}: {k} inválido (ejemplo: {'-8%' if k == 'rate' else '-3Hz'})")
    return e


def errores_palabras(palabras):
    if not isinstance(palabras, list) or not palabras:
        return ["la lista de palabras está vacía o no es una lista"]
    anterior = -1.0
    for p in palabras:
        if (not isinstance(p, dict) or not isinstance(p.get("w"), str) or not p["w"].strip()
                or not numero(p.get("t")) or not numero(p.get("d")) or p["t"] < 0 or p["d"] < 0
                or p["t"] < anterior):
            return ["palabras sin texto, tiempos inválidos o fuera de orden"]
        anterior = p["t"]
    return []


def argumentos_voz(b):
    voz = b.get("voz") or VOCES[b["personaje"]]
    rate, pitch = ("+0%", "+0Hz") if b.get("voz") else PROSODIA.get(b["personaje"], ("+0%", "+0Hz"))
    return b["texto"], voz, b.get("rate", rate), b.get("pitch", pitch)
