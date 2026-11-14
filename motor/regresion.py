"""Prueba de regresión del motor: ¿las escenas de referencia se siguen viendo igual?

Uso (desde la raíz del proyecto/):
    .venv\\Scripts\\python.exe motor\\regresion.py                  renderiza y compara todo con las referencias
    .venv\\Scripts\\python.exe motor\\regresion.py --solo ejemplo    solo las escenas cuyo nombre contiene ese texto
    .venv\\Scripts\\python.exe motor\\regresion.py --guardar         renderiza y GUARDA las referencias (todas, o las de --solo)
    .venv\\Scripts\\python.exe motor\\regresion.py --sin-render      compara el último render (para probar tolerancias)

Qué hace: renderiza cada escena en vista previa (540x960, 15 fps) en una carpeta temporal propia (no toca el
render/ de la escena ni su revision/), saca un fotograma por segundo y lo compara con el guardado en
05-mejora/regresion/<escena>/. Tolera el ruido de compresión: un píxel cuenta como cambiado solo si difiere en
más de TOLERANCIA niveles y tiene vecinos que también cambiaron. Si algo cambió de forma o de posición, dice en
qué escena, en qué segundo y en qué zona, y deja imágenes (referencia | ahora, con el cambio en un recuadro) en
05-mejora/regresion/_diferencias/.

No genera voz: usa el audio/ que ya existe en cada escena (si falta, ejecuta antes producir.py en esa carpeta).
Código de salida: 0 = sin cambios · 1 = hay cambios o errores.
Cuándo se actualiza una referencia: solo cuando el cambio es intencionado y queda documentado en el historial
del proyecto. Nunca se guarda una referencia «para que pase».
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from configuracion import CONFIG, archivos_configuracion

MOTOR = Path(__file__).resolve().parent
RAIZ = MOTOR.parent
REFS = RAIZ / "05-mejora" / "regresion"
DIFS = REFS / "_diferencias"
TMP = Path(tempfile.gettempdir()) / "motor_regresion"   # fuera del proyecto: intermedios regenerables

def cargar_escenas():
    escenas = CONFIG.get("regresion", {}).get("escenas", [])
    if not isinstance(escenas, list) or any(
            not isinstance(e, str) or not e or "\\" in e or Path(e).is_absolute()
            or ":" in e or any(p in ("", ".", "..") for p in e.split("/")) for e in escenas):
        raise ValueError("regresion.escenas debe ser una lista de rutas relativas internas")
    return escenas


ESCENAS = cargar_escenas()
FPS = 15                         # vista previa
ANCHO, ALTO = 270, 480           # tamaño al que se comparan (la mitad de la vista previa: promedia el ruido)
TOLERANCIA = 28                  # niveles (0-255) que puede variar un píxel sin contar como cambio
VECINOS = 4                      # un píxel cambiado cuenta si en su 3x3 hay al menos estos cambiados (quita motas)
MIN_PIXELES = 10                 # píxeles cambiados para avisar de un fotograma
COLUMNAS = ["izquierda", "centro", "derecha"]
FILAS = ["arriba", "centro-arriba", "centro-abajo", "abajo"]


def nombre(esc):
    return esc.replace("/", "__")


def huella(*rutas):
    h = hashlib.sha1()
    for r in rutas:
        h.update(Path(r).read_bytes())
    return h.hexdigest()[:12]


def huella_motor():
    fuentes = {p for p in MOTOR.rglob("*.py") if "_archivo" not in p.parts and "__pycache__" not in p.parts
               and p.name != "regresion.py"}
    return huella(*sorted(fuentes | archivos_configuracion()))


def renderizar(esc):
    """Renderiza la escena en vista previa. Devuelve (video, error)."""
    carpeta = RAIZ / "03-produccion" / esc
    fuente = carpeta / "escena.py"
    if not fuente.exists():
        return None, f"no existe {fuente}"
    if not (carpeta / "audio" / "tiempos.json").exists():
        return None, "falta audio/tiempos.json: ejecuta antes producir.py en esa carpeta"
    clases = re.findall(r"^class (\w+)\(EscenaEstudio\)", fuente.read_text(encoding="utf-8"), re.M)
    if len(clases) != 1:
        return None, f"escena.py debe definir una sola escena, tiene {clases}"
    media = TMP / nombre(esc)
    video = media / "videos" / "escena" / "960p15" / f"{clases[0]}.mp4"
    if video.exists():
        video.unlink()
    env = dict(os.environ, CALIDAD="baja", PYTHONIOENCODING="utf-8", SIN_CHOQUES="1")
    r = subprocess.run([sys.executable, "-m", "manim", "render", "escena.py", clases[0], "--media_dir", str(media),
                        "--disable_caching", "-v", "ERROR", "--progress_bar", "none"],
                       cwd=carpeta, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    salida = (r.stdout or "") + (r.stderr or "")
    if r.returncode or "Traceback" in salida or not video.exists():
        return None, "el render falló:\n       " + "\n       ".join(salida.strip().splitlines()[-6:])
    return video, None


def video_anterior(esc):
    v = list((TMP / nombre(esc) / "videos" / "escena" / "960p15").glob("*.mp4"))
    return (v[0], None) if v else (None, "no hay un render anterior (quita --sin-render)")


def fotogramas(video, destino):
    """Un fotograma por segundo exacto (n = 0, 15, 30...). 0001.png es el segundo 0."""
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-an",
                    "-vf", f"select='not(mod(n\\,{FPS}))',scale={ANCHO}:{ALTO}:flags=area",
                    "-fps_mode", "passthrough", str(destino / "%04d.png")], check=True)
    return sorted(destino.glob("*.png"))


def mascara(a, b):
    """Píxeles que cambiaron de verdad entre dos fotogramas (sin motas de compresión)."""
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2) > TOLERANCIA
    p = np.pad(d, 1).astype(np.uint8)
    alto, ancho = d.shape
    cerca = sum(p[i:i + alto, j:j + ancho] for i in range(3) for j in range(3))
    return d & (cerca >= VECINOS)


def zona(m):
    """Describe dónde está el cambio: nombre de la zona, recuadro en píxeles y en unidades de Manim."""
    ys, xs = np.nonzero(m)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    cx, cy = (x0 + x1) / 2 / ANCHO, (y0 + y1) / 2 / ALTO
    donde = f"{FILAS[min(int(cy * 4), 3)]}-{COLUMNAS[min(int(cx * 3), 2)]}"
    if (x1 - x0) > ANCHO * 0.6 and (y1 - y0) > ALTO * 0.6:
        donde = "casi toda la pantalla"
    mx = lambda x: (x / ANCHO - 0.5) * 9      # noqa: E731  unidades de Manim (cuadro de 9 x 16)
    my = lambda y: (0.5 - y / ALTO) * 16      # noqa: E731
    return donde, (x0, y0, x1, y1), f"x de {mx(x0):+.1f} a {mx(x1):+.1f}, y de {my(y1):+.1f} a {my(y0):+.1f}"


def guardar_diferencia(ref, act, caja, destino):
    lienzo = Image.new("RGB", (ANCHO * 2 + 6, ALTO), "#FF2D55")
    lienzo.paste(ref, (0, 0))
    marcada = act.copy()
    x0, y0, x1, y1 = (int(v) for v in caja)
    ImageDraw.Draw(marcada).rectangle([max(x0 - 3, 0), max(y0 - 3, 0), min(x1 + 3, ANCHO - 1), min(y1 + 3, ALTO - 1)],
                                      outline="#FF2D55", width=2)
    lienzo.paste(marcada, (ANCHO + 6, 0))
    destino.parent.mkdir(parents=True, exist_ok=True)
    lienzo.save(destino)


def comparar(esc, nuevos):
    """Devuelve la lista de hallazgos (vacía = sin cambios)."""
    ref_dir = REFS / nombre(esc)
    viejos = sorted(ref_dir.glob("*.png"))
    if not viejos:
        return [f"no hay referencia guardada: ejecuta con --guardar --solo {esc.split('/')[-1]}"]
    hallazgos = []
    if len(viejos) != len(nuevos):
        hallazgos.append(f"cambió la duración: la referencia dura {len(viejos)} s y ahora {len(nuevos)} s")
    malos = []   # (segundo, píxeles, zona, coords)
    for v, n in zip(viejos, nuevos):
        ref, act = Image.open(v).convert("RGB"), Image.open(n).convert("RGB")
        m = mascara(np.asarray(ref), np.asarray(act))
        if m.sum() >= MIN_PIXELES:
            donde, caja, coords = zona(m)
            seg = int(v.stem) - 1
            malos.append((seg, int(m.sum()), donde, coords))
            guardar_diferencia(ref, act, caja, DIFS / nombre(esc) / f"seg{seg:03d}.png")
    # agrupa segundos seguidos con la misma zona
    i = 0
    while i < len(malos):
        j = i
        while j + 1 < len(malos) and malos[j + 1][0] == malos[j][0] + 1 and malos[j + 1][2] == malos[i][2]:
            j += 1
        peor = max(malos[i:j + 1], key=lambda x: x[1])
        cuando = f"segundo {malos[i][0]}" if i == j else f"segundos {malos[i][0]} a {malos[j][0]}"
        hallazgos.append(f"{cuando}: cambio en la zona {peor[2]} ({peor[3]}; {peor[1] * 100 / (ANCHO * ALTO):.2f} % de la "
                         f"imagen en el segundo {peor[0]})")
        i = j + 1
    return hallazgos


def main():
    ap = argparse.ArgumentParser(description="Prueba de regresión visual del motor")
    ap.add_argument("--guardar", action="store_true", help="guardar las referencias en vez de comparar")
    ap.add_argument("--solo", default="", help="solo las escenas cuyo nombre contiene este texto")
    ap.add_argument("--sin-render", action="store_true", help="reutilizar el último render")
    ap.add_argument("--paralelo", type=int, default=2, help="renders a la vez (por defecto 2)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    escenas = [e for e in ESCENAS if a.solo in e]
    if not escenas:
        print(f"Ninguna escena contiene «{a.solo}». Disponibles: {', '.join(ESCENAS)}")
        sys.exit(1)
    inicio = time.time()
    if not a.guardar:
        for e in escenas:
            shutil.rmtree(DIFS / nombre(e), ignore_errors=True)
    print(f"Renderizando {len(escenas)} escena(s) en vista previa…" if not a.sin_render else "Usando el último render…")
    with ThreadPoolExecutor(max_workers=max(1, a.paralelo)) as pool:
        videos = list(pool.map(video_anterior if a.sin_render else renderizar, escenas))

    resultado, lineas = True, []
    for esc, (video, error) in zip(escenas, videos):
        if error:
            resultado = False
            print(f"[ERROR]   {esc}: {error}")
            lineas.append(f"- **{esc}** — ERROR: {error.splitlines()[0]}")
            continue
        nuevos = fotogramas(video, TMP / nombre(esc) / "fotogramas")
        if a.guardar:
            destino = REFS / nombre(esc)
            shutil.rmtree(destino, ignore_errors=True)
            destino.mkdir(parents=True)
            for f in nuevos:
                shutil.copy2(f, destino / f.name)
            (destino / "referencia.json").write_text(json.dumps({
                "escena": esc, "guardada": time.strftime("%Y-%m-%d %H:%M"), "fotogramas": len(nuevos),
                "huella_motor": huella_motor(), "huella_escena": huella(RAIZ / "03-produccion" / esc / "escena.py"),
                "tolerancia": TOLERANCIA}, indent=1, ensure_ascii=False), encoding="utf-8")
            print(f"[GUARDADA] {esc}: {len(nuevos)} fotogramas")
            lineas.append(f"- **{esc}** — referencia guardada ({len(nuevos)} fotogramas)")
            continue
        hallazgos = comparar(esc, nuevos)
        if hallazgos:
            resultado = False
            print(f"[CAMBIOS] {esc}")
            for h in hallazgos:
                print(f"            {h}")
            aviso = ""
            meta = REFS / nombre(esc) / "referencia.json"
            if meta.exists() and json.loads(meta.read_text(encoding="utf-8")).get("huella_escena") != huella(
                    RAIZ / "03-produccion" / esc / "escena.py"):
                aviso = " (ojo: `escena.py` cambió desde que se guardó la referencia; puede no ser culpa del motor)"
                print("            ojo: escena.py cambió desde que se guardó la referencia")
            lineas.append(f"- **{esc}** — CAMBIOS{aviso}. Imágenes en `05-mejora/regresion/_diferencias/{nombre(esc)}/`")
            lineas += [f"  - {h}" for h in hallazgos]
        else:
            print(f"[IGUAL]   {esc}: {len(nuevos)} fotogramas")
            lineas.append(f"- **{esc}** — sin cambios ({len(nuevos)} fotogramas)")

    seg = time.time() - inicio
    if a.guardar:
        veredicto = "REFERENCIAS GUARDADAS" if resultado else "NO SE GUARDARON TODAS LAS REFERENCIAS"
    else:
        veredicto = "SIN CAMBIOS" if resultado else "HAY CAMBIOS"
    REFS.mkdir(parents=True, exist_ok=True)
    (REFS / "ultimo-informe.md").write_text("\n".join(
        [f"# Regresión del motor · {time.strftime('%Y-%m-%d %H:%M')}", "",
         f"**{veredicto}** · {seg:.0f} s · huella del motor `{huella_motor()}` · tolerancia {TOLERANCIA} niveles", ""]
        + lineas) + "\n", encoding="utf-8")
    print(f"\n{veredicto} ({seg:.0f} s). Informe: 05-mejora/regresion/ultimo-informe.md")
    if not resultado and not a.guardar:
        print("Mira las imágenes de 05-mejora/regresion/_diferencias/ (izquierda: referencia · derecha: ahora).\n"
              "Si el cambio NO era intencionado, arregla el motor. Si lo era, explícalo y vuelve a guardar con --guardar.")
    sys.exit(0 if resultado else 1)


if __name__ == "__main__":
    main()
