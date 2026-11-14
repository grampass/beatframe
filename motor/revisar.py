"""Hojas de revisión de un video.

Uso:  .venv\\Scripts\\python.exe motor\\revisar.py 03-produccion\\<carpeta> <video.mp4> [segundo_inicial] [b6-b8]
Crea en <carpeta>/revision/:
  contacto.png          vista general: un fotograma pequeño por beat, a MITAD de cada frase
  finales_NN.png        el FINAL de cada beat a tamaño legible (5 por hoja). Es el momento más cargado: los rótulos
                        se acumulan al terminar la frase. Si hay revision/choques.json, cada problema detectado
                        (motor/choques.py) sale con un recuadro rojo.

`segundo_inicial` y el tramo solo se usan con el render por tramos (producir.py --beats): el video empieza en ese
segundo del guion y solo contiene esos beats.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
POR_HOJA = 5


def fotograma(video, t, destino):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(t, 0):.2f}", "-i", str(video), "-frames:v", "1", str(destino)], check=True)
    return Image.open(destino).convert("RGB")


def main(carpeta: Path, video: Path, desde=0.0, tramo=None, destino=None, choques_ruta=None):
    from nucleo import Guion
    g = Guion(carpeta)
    out = Path(destino) if destino else carpeta / "revision"
    out.mkdir(exist_ok=True, parents=True)
    f_choques = Path(choques_ruta) if choques_ruta else out / "choques.json"
    beats = g.beats
    if tramo:
        a, _, b = tramo.partition("-")
        ids = [x["id"] for x in beats]
        beats = beats[ids.index(a):ids.index(b or a) + 1]
    tmp = out / "_tmp.png"

    # --- vista general (mitad de cada beat) ---
    minis = [fotograma(video, (b["ini"] + b["fin"]) / 2 - desde, tmp).resize((360, 640)) for b in beats]
    hoja = Image.new("RGB", (360 * len(minis), 640))
    for i, m in enumerate(minis):
        hoja.paste(m, (360 * i, 0))
    hoja.save(out / "contacto.png")

    # --- finales de beat, con los choques marcados ---
    choques = []
    if f_choques.exists():
        choques = json.loads(f_choques.read_text(encoding="utf-8"))["hallazgos"]
    for viejo in out.glob("finales_*.png"):
        viejo.unlink()
    finales = []
    originales = []
    contraste_avisos, zonas_avisos = [], []
    muestras = json.loads(f_choques.read_text(encoding="utf-8")).get("muestras", []) if f_choques.exists() else []
    from contraste import estimar
    from zonas import superponer, perfil, contiene, normalizar
    for b in beats:
        im = fotograma(video, b["fin"] - 0.14 - desde, tmp)
        originales.append(im.copy())
        fotos = [m for m in muestras if m["beat"] == b["id"]]
        objetos = min(fotos, key=lambda m: abs(m["t"]-b["fin"]+0.14))["objetos"] if fotos else []
        for o in objetos:
            if o["tipo"] == "texto":
                aviso = estimar(im, o)
                if aviso:
                    aviso["beat"] = b["id"]
                    contraste_avisos.append(aviso)
            for nombre in ("youtube", "tiktok", "instagram", "facebook"):
                if not contiene(normalizar(o["caja"]), nombre, tolerancia=0.002):
                    zonas_avisos.append(dict(beat=b["id"], perfil=nombre, texto=o["nombre"], caja=o["caja"]))
        w, h = im.size
        d = ImageDraw.Draw(im)
        n = 0
        for v in choques:
            c = v["cajas"].get(b["id"])
            if c and v["tipo"] not in ("exceso", "pequeno"):
                x0, y0, x1, y1 = (c[0] + 4.5) / 9 * w, (8 - c[3]) / 16 * h, (c[2] + 4.5) / 9 * w, (8 - c[1]) / 16 * h
                d.rectangle([x0 - 3, y0 - 3, x1 + 3, y1 + 3], outline="#FF2D55", width=3)
                n += 1
        d.rectangle([0, h - 34, w, h], fill="#000000")
        d.text((10, h - 27), f"{b['id']} · final ({b['fin']:.1f} s)" + (f" · {n} problema(s) marcados" if n else ""), fill="#FFFFFF")
        finales.append(im)
    for k in range(0, len(finales), POR_HOJA):
        grupo = finales[k:k + POR_HOJA]
        w, h = grupo[0].size
        hoja = Image.new("RGB", (w * len(grupo) + 6 * (len(grupo) - 1), h), "#FF2D55")
        for i, im in enumerate(grupo):
            hoja.paste(im, ((w + 6) * i, 0))
        hoja.save(out / f"finales_{k // POR_HOJA + 1:02d}.png")
        for nombre in ("youtube", "tiktok", "instagram", "facebook"):
            mascara = Image.new("RGB", hoja.size, "#16181F")
            for i, im in enumerate(originales[k:k+POR_HOJA]):
                mascara.paste(superponer(im, nombre), ((w+6)*i, 0))
            mascara.save(out / f"zonas_{nombre}_{k // POR_HOJA + 1:02d}.png")
    (out / "zonas.json").write_text(json.dumps(dict(perfiles={n:perfil(n) for n in ("youtube", "tiktok", "instagram", "facebook")},
                                                    avisos=zonas_avisos), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (out / "contraste.json").write_text(json.dumps(dict(metodo="estimación sobre el fotograma; inspección humana obligatoria",
                                                        avisos=contraste_avisos), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    tmp.unlink(missing_ok=True)

    for b in beats:
        print(f"{b['id']}  {b['ini']:5.2f}-{b['fin']:5.2f} s  {b['texto']}")
    print(f"Total {g.total:.1f} s -> {out / 'contacto.png'} y {len(range(0, len(finales), POR_HOJA))} hoja(s) finales_NN.png")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3]) if len(sys.argv) > 3 else 0.0,
         (sys.argv[4] or None) if len(sys.argv) > 4 else None,
         sys.argv[5] if len(sys.argv) > 5 else None, sys.argv[6] if len(sys.argv) > 6 else None)
