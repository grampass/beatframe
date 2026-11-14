"""Filtro de pronunciación de las voces.

Las voces multilingües son extranjeras leyendo español y a veces se les escapa
una palabra («Preparé.» sonó «Preparo», «Moví» sonó «Móvil»). Este filtro escucha cada beat con un reconocedor
local (faster-whisper, modelo «small», español), compara lo que oye con el guion y además mira el léxico de palabras de
riesgo (configurado externamente). Para cada palabra marcada genera variantes (coma detrás, coma delante, más lenta),
las vuelve a escuchar y arma UNA escucha para el control B. No cambia el guion: el usuario elige.

Uso:  .venv\\Scripts\\python.exe motor\\pronunciacion.py 03-produccion\\<carpeta> [--sin-variantes]
Antes: la voz generada (producir.py o tts.py). Crea:
  audio/pronunciacion.json                       lo oído por beat (caché por huella del audio)
  pruebas-voz/pronunciacion/<beat>-<n>.mp3       variantes de los beats marcados
  pruebas-voz/pronunciacion/escucha.mp3 + .md    escucha única con la lista numerada
Termina con código 0 aunque marque palabras (es un aviso para B, no un bloqueo); 1 si no puede escuchar.
"""
import asyncio
import difflib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

MOTOR = Path(__file__).resolve().parent
sys.path.insert(0, str(MOTOR))
from artefactos import escribir_json, leer_json, sha256      # noqa: E402
from contrato import argumentos_voz                          # noqa: E402

from configuracion import ruta
LEXICO = ruta("lexico_voz", MOTOR / "recursos" / "lexico.json")
MODELO = "small"
_modelo = None


# ---------- comparación (sin red ni modelo: la cubren las pruebas) ----------
def normalizar(w):
    """Forma «como suena» en español neutro: sin tildes, seseo, b=v, sin h, ll=y. Así «tasa»=«taza» y «tu»=«tú»
    no se marcan; «preparo» o «móvil» frente a «preparé»/«moví» sí."""
    w = re.sub(r"[^\wñ]", "", w.lower())
    w = "".join(c for c in unicodedata.normalize("NFD", w.replace("ñ", "\0")) if unicodedata.category(c) != "Mn")
    w = w.replace("\0", "ñ")
    for a, b in (("ll", "y"), ("v", "b"), ("z", "s"), ("ce", "se"), ("ci", "si"), ("qu", "k"), ("c", "k"), ("h", "")):
        w = w.replace(a, b)
    return w


def palabras_texto(texto):
    """[(palabra, inicio_en_texto, fin, abre_frase)] en el orden del guion."""
    out, inicio = [], True
    for m in re.finditer(r"[^\W\d_]+", texto):
        previo = texto[out[-1][2]:m.start()] if out else texto[:m.start()]
        abre = inicio or bool(re.search(r"[.!?¿¡]", previo))
        out.append((m.group(), m.start(), m.end(), abre))
        inicio = False
    return out


def comparar(texto, oidas):
    """Palabras del guion que el reconocedor no oyó (reemplazadas u omitidas). `oidas`: lista de palabras."""
    gu = palabras_texto(texto)
    a, b = [normalizar(p[0]) for p in gu], [normalizar(w) for w in oidas]
    b = [w for w in b if w]
    marcas = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op in ("replace", "delete"):
            oido = " ".join(oidas_limpias(oidas)[j1:j2]) if op == "replace" else ""
            for i in range(i1, i2):
                marcas.append(dict(i=i, palabra=gu[i][0], oido=oido or "(no se oye)", motivo="reconocedor"))
    return marcas


def oidas_limpias(oidas):
    return [w.strip(" ,.;:!?¡¿«»\"'") for w in oidas if normalizar(w)]


def riesgos(texto, personaje, lexico):
    """Palabras del léxico de riesgo presentes en el texto que no estén cubiertas por una frase ya aprobada."""
    marcas, low = [], texto.lower()
    cubiertas = [(low.find(f.lower()), low.find(f.lower()) + len(f)) for f in lexico.get("aprobadas", []) if f.lower() in low]
    for i, (w, ini, fin, abre) in enumerate(palabras_texto(texto)):
        r = lexico.get("riesgo", {}).get(w.lower())
        if not r or (r.get("voz") and r["voz"] != personaje) or (r.get("solo_inicio") and not abre):
            continue
        if any(a <= ini and fin <= b for a, b in cubiertas):
            continue
        marcas.append(dict(i=i, palabra=w, oido="—", motivo=f"léxico: {r.get('nota', 'riesgo conocido')}"))
    return marcas


def variantes_texto(texto, i):
    """Textos alternativos que solo cambian la puntuación alrededor de la palabra i (el sentido no cambia)."""
    gu = palabras_texto(texto)
    w, ini, fin, abre = gu[i]
    out = []
    if fin < len(texto) and not re.match(r"\s*[,.;:!?…]", texto[fin:]):
        out.append(("coma detrás", texto[:fin] + "," + texto[fin:]))
    if not abre and not re.search(r"[,;:]\s*$", texto[:ini]):
        out.append(("coma delante", texto[:ini].rstrip() + ", " + texto[ini:]))
    return out


def mas_lento(rate, paso=6):
    n = int(re.fullmatch(r"([+-]?\d+)%", rate).group(1)) - paso
    return f"{n:+d}%"


# ---------- escucha (necesita el modelo) ----------
def escuchar(ruta):
    global _modelo
    if _modelo is None:
        import logging
        import warnings
        warnings.filterwarnings("ignore")
        logging.getLogger("faster_whisper").setLevel(logging.ERROR)
        from faster_whisper import WhisperModel
        _modelo = WhisperModel(MODELO, device="cpu", compute_type="int8")
    segs, _ = _modelo.transcribe(str(ruta), language="es", word_timestamps=True, beam_size=5,
                                 condition_on_previous_text=False, vad_filter=False)
    return [w.word.strip() for s in segs for w in s.words]


def revisar_beat(b, ruta, lexico, cache):
    h = sha256(ruta)
    if cache.get(b["id"], {}).get("sha256") != h:
        cache[b["id"]] = dict(sha256=h, oido=escuchar(ruta))
    oido = cache[b["id"]]["oido"]
    marcas = {m["i"]: m for m in riesgos(b["texto"], b.get("personaje"), lexico)}
    for m in comparar(b["texto"], oido):
        marcas[m["i"]] = m                                   # lo oído manda sobre el léxico
    return sorted(marcas.values(), key=lambda m: m["i"]), oido


async def _variantes(b, marcas, destino):
    from tts import decir
    texto, voz, rate, pitch = argumentos_voz(b)
    pedidas, vistos = [], set()
    for m in marcas:
        for nombre, t in variantes_texto(texto, m["i"]):
            if t not in vistos:
                vistos.add(t)
                pedidas.append((f"{nombre} de «{m['palabra']}»", t, rate))
    pedidas.append(("más lenta (solo prosodia)", texto, mas_lento(rate)))
    hechas = []
    for n, (nombre, t, r) in enumerate(pedidas, 2):
        ruta = destino / f"{b['id']}-{n}.mp3"
        try:
            await decir(t, voz, r, pitch, ruta, intentos=6)
        except RuntimeError:                                 # edge-tts falla a ratos: se omite esa variante y se avisa
            print(f"  {b['id']}: no se pudo generar la variante «{nombre}»; se omite")
            continue
        oido = escuchar(ruta)
        fallan = {m["palabra"].lower() for m in comparar(t, oido)}
        siguen = [x["palabra"] for x in marcas if x["palabra"].lower() in fallan]
        hechas.append(dict(n=n, que=nombre, texto=t, rate=r, ruta=ruta, oido=" ".join(oido), siguen=siguen))
    return hechas


def unir(rutas, salida, silencio=0.9):
    lista = []
    for r in rutas:
        lista += ["-i", str(r)]
    n = len(rutas)
    filtro = "".join(f"[{k}:a]aresample=24000,aformat=channel_layouts=mono,apad=pad_dur={silencio}[a{k}];" for k in range(n))
    filtro += "".join(f"[a{k}]" for k in range(n)) + f"concat=n={n}:v=0:a=1[o]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *lista, "-filter_complex", filtro, "-map", "[o]", str(salida)],
                   check=True, capture_output=True)


def main(carpeta, con_variantes=True):
    carpeta = Path(carpeta)
    guion = json.loads((carpeta / "guion.json").read_text(encoding="utf-8"))
    lexico = leer_json(LEXICO, {}) or {}
    f_cache = carpeta / "audio" / "pronunciacion.json"
    cache = leer_json(f_cache, {}) or {}
    marcados = []
    for b in guion["beats"]:
        ruta = carpeta / "audio" / f"{b['id']}.mp3"
        if not ruta.is_file():
            raise FileNotFoundError(f"{b['id']}: falta la voz; genera antes con producir.py")
        marcas, oido = revisar_beat(b, ruta, lexico, cache)
        escribir_json(f_cache, cache)
        if marcas:
            marcados.append((b, marcas, oido))
    print(f"Pronunciación: {len(guion['beats'])} beats escuchados, {len(marcados)} con palabras marcadas")
    for b, marcas, oido in marcados:
        print(f"  {b['id']}: " + "; ".join(f"«{m['palabra']}» → {m['oido']} ({m['motivo']})" for m in marcas))
    if not marcados or not con_variantes:
        return marcados
    destino = carpeta / "pruebas-voz" / "pronunciacion"
    destino.mkdir(parents=True, exist_ok=True)
    rutas, lineas, k = [], [f"# Escucha de pronunciación · {guion.get('id', carpeta.name)}", "",
                            "Generada por `motor/pronunciacion.py`. Cada beat marcado suena primero tal cual y luego sus "
                            "variantes, separadas por un silencio. El usuario elige una por beat en el control B "
                            "(o la original). Lo que dice el reconocedor orienta; la última palabra es del oído humano. "
                            "Las marcas del léxico no las puede comprobar el reconocedor.", ""], 0
    for b, marcas, oido in marcados:
        hechas = asyncio.run(_variantes(b, marcas, destino))
        lineas.append(f"## {b['id']} · marcadas: " + ", ".join(f"«{m['palabra']}» (se oye: {m['oido']})" for m in marcas))
        k += 1
        rutas.append(carpeta / "audio" / f"{b['id']}.mp3")
        lineas.append(f"{k}. **original** · {b['texto']} · se oye: {' '.join(oido)}")
        for h in hechas:
            k += 1
            rutas.append(h["ruta"])
            lineas.append(f"{k}. {h['que']} · {h['texto']} · rate {h['rate']} · {'el reconocedor ya no confunde nada' if not h['siguen'] else 'aún confunde ' + ', '.join(h['siguen'])}"
                          f" · se oye: {h['oido']}")
        inicio = [m["palabra"] for m in marcas if palabras_texto(b["texto"])[m["i"]][3]]
        if inicio:
            lineas.append(f"Abren frase: {', '.join(inicio)}. La puntuación no suele bastar: pedir a Codex una palabra "
                          "delante («Yo preparé», «Yo moví»).")
        lineas.append("")
    unir(rutas, destino / "escucha.mp3")
    (destino / "escucha.md").write_text("\n".join(lineas), encoding="utf-8")
    print(f"Escucha: {destino / 'escucha.mp3'} ({k} tomas; lista en escucha.md)")
    return marcados


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    try:
        main(Path(sys.argv[1]), con_variantes="--sin-variantes" not in sys.argv)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as e:
        print(f"ERROR PRONUNCIACIÓN: {e}")
        sys.exit(1)
