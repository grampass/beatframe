"""Producción por etapas: validar, preparar voz, comprobar sin dibujar, renderizar y reutilizar resultados.
Un informe técnico no concede controles editoriales ni permiso de publicar.
"""
import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
import traceback
import uuid
from fractions import Fraction
from pathlib import Path

MOTOR = Path(__file__).resolve().parent
sys.path.insert(0, str(MOTOR))
from artefactos import Bloqueo, CacheEtapas, escribir_json, firma, leer_json, sha256
from flujo import (Informe, cerrado, dependencias, eventos_reutilizados, plan_firma, preparar_revision)
from validar import validar

PY = sys.executable
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def correr(cmd, cwd=None, env=None):
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def clase_escena(fuente):
    arbol = ast.parse(fuente.read_text(encoding="utf-8"), filename=str(fuente))
    clases = [n.name for n in arbol.body if isinstance(n, ast.ClassDef) and
              any(isinstance(b, ast.Name) and b.id == "EscenaEstudio" for b in n.bases)]
    if len(clases) != 1:
        raise ValueError(f"escena.py debe definir una clase EscenaEstudio; encontradas: {clases}")
    return clases[0]


def ejecutar_escena(carpeta, clase, run, final, sonido, perfil, solo=False, tramo=None):
    datos = run / ("previo" if solo else "render-datos")
    datos.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, CALIDAD="alta" if final else "baja", PYTHONIOENCODING="utf-8",
               SONIDO="1" if sonido else "0", PERFIL_ZONA=perfil or "", REVISION_DIR=str(datos))
    for k in ("BEATS", "SOLO_CHOQUES", "SIN_CHOQUES"):
        env.pop(k, None)
    if solo:
        env["SOLO_CHOQUES"] = "1"
    elif tramo:
        env["BEATS"] = tramo
    media = run / "media"
    orden = [PY, "-m", "manim", "render", "escena.py", clase, "--media_dir", media,
             "--disable_caching", "-v", "ERROR", "--progress_bar", "none"]
    if solo:
        orden.append("--dry_run")
    cod, log = correr(orden, cwd=carpeta, env=env)
    (run / ("previo.log" if solo else "render.log")).write_text(log, encoding="utf-8")
    if cod or "Traceback" in log:
        raise ValueError(f"{'Comprobación' if solo else 'Render'} falló; ver {run.name}/"
                         f"{'previo' if solo else 'render'}.log: " + " ".join(log.splitlines()[-3:]))
    for nombre in ("choques.json", "tiempos-escena.json"):
        if not (datos / nombre).is_file():
            raise ValueError(f"La escena no generó {nombre}")
    if sonido and not (datos / "sonido-eventos.json").is_file():
        raise ValueError("La escena no generó los eventos sonoros")
    if not sonido:
        escribir_json(datos / "sonido-eventos.json", dict(ambientes=[], efectos=[], pistas=[]))
    video = media / "videos" / "escena" / ("1920p30" if final else "960p15") / f"{clase}.mp4"
    if not solo and not video.is_file():
        raise ValueError("El render no produjo el MP4 esperado")
    return datos, video


def comprobar_escena(datos, info, codigo, seleccion=None):
    composicion = leer_json(datos / "choques.json", {}) or {}
    if not isinstance(composicion.get("hallazgos"), list):
        return info.paso(codigo, False, "Informe de composición inválido")
    hs = composicion["hallazgos"]
    retrasos = (leer_json(datos / "tiempos-escena.json", {}) or {}).get("retrasos", [])
    if seleccion:
        hs = [h for h in hs if set(h.get("beats", [])) & set(seleccion)]
        retrasos = [h for h in retrasos if h.get("beat") in seleccion]
    info.datos["hallazgos"] = dict(composicion=len(hs), retrasos=len(retrasos), detalle=str(datos))
    return info.paso(codigo, not hs and not retrasos,
                     f"{len(hs)} de composición; {len(retrasos)} retrasos. " +
                     "; ".join(h.get("texto", str(h)) for h in hs[:3]))


def comprobar_video(video, final, esperado=None):
    from sonido import completar_audio
    d = completar_audio(video)
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,width,height,r_frame_rate,duration",
                        "-of", "json", str(video)], capture_output=True, text=True, check=True)
    meta = json.loads(r.stdout)
    v = next((s for s in meta["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in meta["streams"] if s["codec_type"] == "audio"), {})
    w, h, fps = (1080, 1920, 30) if final else (540, 960, 15)
    errores = []
    if (v.get("width"), v.get("height")) != (w, h) or abs(float(Fraction(v.get("r_frame_rate", "0"))) - fps) > 0.001:
        errores.append(f"formato esperado {w}×{h} a {fps} fps")
    if not a or abs(d.get("audio", 0) - d.get("video", 0)) > 0.1:
        errores.append("audio ausente o duración desalineada")
    if esperado is not None and abs(d.get("video", 0) - esperado) >= 0.8:
        errores.append(f"duración distinta del guion ({esperado:.3f} s)")
    if errores:
        raise ValueError("; ".join(errores))
    return d


def main(carpeta, final=False, solo_choques=False, tramo=None, sonido=None, perfil_zona=None, forzar=False):
    carpeta = Path(carpeta).resolve()
    # Se comprueba el cierre antes de crear carpetas, locks o informes.
    if cerrado(carpeta):
        print("PRODUCCION_CERRADA: video publicado; las mejoras se prueban en una producción nueva.")
        return 1
    if not carpeta.is_dir():
        print("CARPETA_INEXISTENTE")
        return 1
    try:
        with Bloqueo(carpeta / "revision" / ".produccion.lock"):
            return _producir(carpeta, final, solo_choques, tramo, sonido, perfil_zona, forzar)
    except (OSError, RuntimeError) as e:
        print(f"PRODUCCION_OCUPADA: {e}")
        return 1


def _producir(carpeta, final, solo_choques, tramo, sonido, perfil_zona, forzar):
    rid = uuid.uuid4().hex[:12]
    run = carpeta / "revision" / "ejecuciones" / rid
    run.mkdir(parents=True)
    info = Informe(carpeta, "composición" if solo_choques else "final" if final else "vista previa", rid)
    try:
        errores, avisos = validar(carpeta, estricto=final)
        for a in avisos:
            info.aviso(getattr(a, "codigo", "GUION_AVISO"), a)
        if not info.paso("GUION_VALIDO", not errores, "; ".join(errores)):
            return info.terminar()
        clase = clase_escena(carpeta / "escena.py")
        g = json.loads((carpeta / "guion.json").read_text(encoding="utf-8"))
        seleccion = None
        if tramo:
            ids = [b["id"] for b in g["beats"]]
            a, _, b = tramo.partition("-")
            if a not in ids or (b or a) not in ids or ids.index(a) > ids.index(b or a):
                raise ValueError("Tramo inexistente o invertido")
            seleccion = ids[ids.index(a):ids.index(b or a) + 1]
        plan_existe = (carpeta / "sonido.json").is_file()
        audio_activo = (plan_existe or g.get("sonido") is True) if sonido is None else sonido
        if tramo and audio_activo:
            if sonido is True:
                raise ValueError("--sonido requiere video completo; el audio de un tramo es orientativo")
            audio_activo = False
            info.aviso("TRAMO_SIN_MEZCLA", "Tramo solo visual; su audio no representa la mezcla completa")
        elif not audio_activo and plan_existe:
            info.aviso("SONIDO_OMITIDO", "Existe sonido.json pero se pidió conservar solo las voces")
        orden_voz = [PY, MOTOR / "tts.py", carpeta] + (["--comprobar"] if solo_choques else [])
        cod, log = correr(orden_voz)
        (run / "voz.log").write_text(log, encoding="utf-8")
        if not info.paso("AUDIO_VIGENTE", cod == 0, " ".join(log.splitlines()[-1:])):
            return info.terminar()
        info.datos["voz"] = leer_json(carpeta / "audio" / "resumen-voz.json", {})
        errores, avisos = validar(carpeta, con_audio=True, estricto=final)
        bloqueos = [a for a in avisos if getattr(a, "bloqueante", False)]
        for a in avisos:
            if a not in [v["mensaje"] for v in info.avisos]:
                info.aviso(getattr(a, "codigo", "GUION_AVISO"), a)
        if not info.paso("TIEMPOS_VALIDOS", not errores and not bloqueos, "; ".join(errores + bloqueos)):
            return info.terminar()
        entrada = dependencias(carpeta)
        clave_fuentes = firma(entrada)
        clave_base = firma(dict(entradas=entrada, final=final, tramo=tramo, sonido=audio_activo, perfil=perfil_zona))
        clave_pre = firma(dict(base=clave_base, plan=plan_firma(carpeta)))
        escribir_json(run / "entradas.json", entrada)
        info.datos["firmas"] = dict(entradas=clave_fuentes, imagen=clave_base, plan=plan_firma(carpeta))
        info.datos["firmas"].update(guion=sha256(carpeta / "guion.json"), escena=sha256(carpeta / "escena.py"))
        cache = CacheEtapas(carpeta / "revision" / "cache-etapas.json", automatico=False)
        previo = None if forzar else cache.vigente("previo", clave_pre)
        if previo:
            pre_dir = Path(previo["meta"]["directorio"])
            info.paso("COMPROBACION_PREVIA", True, str(pre_dir), reutilizado=True)
        else:
            pre_dir, _ = ejecutar_escena(carpeta, clase, run, final, audio_activo, perfil_zona, solo=True)
            if not comprobar_escena(pre_dir, info, "COMPROBACION_PREVIA", seleccion):
                return info.terminar()
            cache.guardar("previo", clave_pre, list(pre_dir.glob("*.json")), directorio=str(pre_dir))
        if solo_choques:
            if not info.paso("FUENTES_ESTABLES", firma(dependencias(carpeta)) == clave_fuentes and
                             plan_firma(carpeta) == info.datos["firmas"]["plan"], "Sin cambios durante la comprobación"):
                return info.terminar()
            cache.confirmar()
            info.datos["composicion"] = str(pre_dir / "choques.json")
            return info.terminar()
        base = None if forzar else cache.vigente("base", clave_base)
        eventos = None
        if base:
            anteriores = Path(base["meta"]["previo"])
            reales = Path(base["meta"]["datos"])
            eventos = eventos_reutilizados(leer_json(anteriores / "sonido-eventos.json", {}),
                                           leer_json(reales / "sonido-eventos.json", {}),
                                           leer_json(pre_dir / "sonido-eventos.json", {}))
            if eventos is None:
                base = None  # Cambió algo más que ganancias: no aproximar marcas del render real.
        if base:
            video_base = Path(base["meta"]["video"])
            real_dir = Path(base["meta"]["datos"])
            info.paso("RENDER_BASE", True, str(video_base), reutilizado=True)
        else:
            real_dir, video_base = ejecutar_escena(carpeta, clase, run, final, audio_activo, perfil_zona, tramo=tramo)
            if not comprobar_escena(real_dir, info, "COMPROBACION_RENDER", seleccion):
                return info.terminar()
            info.paso("RENDER_BASE", True, str(video_base))
            eventos = leer_json(real_dir / "sonido-eventos.json", {})
        desde = (leer_json(real_dir / "choques.json", {}) or {}).get("inicio_tramo", 0.0)
        from nucleo import Guion
        guion = Guion(carpeta)
        esperado = None if tramo else guion.total
        # Normaliza una vez el base y actualiza su firma antes de mezclar/reutilizarlo.
        comprobar_video(video_base, final, esperado)
        cache.guardar("base", clave_base, [video_base, *real_dir.glob("*.json")],
                      video=str(video_base), datos=str(real_dir),
                      previo=str(pre_dir) if not base else base["meta"]["previo"])
        video = video_base
        if audio_activo:
            escribir_json(run / "eventos-mezcla.json", eventos)
            clave_mezcla = firma(dict(base=clave_base, video=sha256(video_base), eventos=eventos,
                                      pistas={p["archivo"]: sha256(p["archivo"]) for p in eventos.get("pistas", [])}))
            mezcla = None if forzar else cache.vigente("mezcla", clave_mezcla)
            if mezcla:
                video = Path(mezcla["meta"]["video"])
                info.paso("MEZCLA", True, str(video), reutilizado=True)
            else:
                from sonido import mezclar
                video = run / "mezcla.mp4"
                medidas = mezclar(video_base, video, guion, run / "eventos-mezcla.json", desde=desde)
                info.paso("MEZCLA", True, f"Pico de acompañamiento {medidas['pico_acompanamiento']:.4f}")
        duraciones = comprobar_video(video, final, esperado)
        if audio_activo and not mezcla:
            cache.guardar("mezcla", clave_mezcla, [video, video.with_suffix(".sonido.json")], video=str(video))
        info.paso("FORMATO_Y_AUDIO", True, f"video {duraciones['video']:.3f} s; audio {duraciones['audio']:.3f} s")
        clave_hojas = firma(dict(base=clave_base, video=sha256(video_base), datos=sha256(real_dir / "choques.json"), tramo=tramo))
        hojas = None if forzar else cache.vigente("hojas", clave_hojas)
        if hojas:
            hojas_dir = Path(hojas["meta"]["directorio"])
            info.paso("HOJAS_REVISION", True, str(hojas_dir), reutilizado=True)
        else:
            hojas_dir = run / "hojas"
            cod, log = correr([PY, MOTOR / "revisar.py", carpeta, video_base, str(desde), tramo or "",
                               hojas_dir, real_dir / "choques.json"])
            (run / "hojas.log").write_text(log, encoding="utf-8")
            if not info.paso("HOJAS_REVISION", cod == 0 and (hojas_dir / "contacto.png").is_file(),
                             str(hojas_dir) if cod == 0 else log[-250:]):
                return info.terminar()
            cache.guardar("hojas", clave_hojas, list(hojas_dir.glob("*")), directorio=str(hojas_dir))
        info.datos["hojas"] = str(hojas_dir)
        # No mezclar fuentes que cambiaron mientras se ejecutaba el comando.
        if not info.paso("FUENTES_ESTABLES", firma(dependencias(carpeta)) == clave_fuentes and
                         plan_firma(carpeta) == info.datos["firmas"]["plan"],
                         "La entrada debe coincidir con la registrada al comenzar"):
            return info.terminar()
        cache.confirmar()
        # Publicar referencias cómodas a la revisión actual, sin eliminar hojas de ejecuciones antiguas.
        for p in hojas_dir.glob("*"):
            if p.is_file():
                shutil.copy2(p, carpeta / "revision" / p.name)
        for nombre in ("choques.json", "tiempos-escena.json"):
            shutil.copy2(real_dir / nombre, carpeta / "revision" / nombre)
        if audio_activo:
            escribir_json(carpeta / "revision" / "sonido-eventos.json", eventos)
        info.datos["revision_visual"] = preparar_revision(carpeta, clave_base)
        if not tramo:
            destino = carpeta / ("final.mp4" if final else "vista-previa.mp4")
            temporal = run / "entrega.mp4"
            shutil.copy2(video, temporal)
            os.replace(temporal, destino)
            info.datos["entrega"] = dict(archivo=str(destino), sha256=sha256(destino))
            info.paso("ENTREGA_ACTUALIZADA", True, destino.name)
        else:
            info.datos["tramo"] = dict(beats=tramo, video=str(video), publicable=False)
        return info.terminar()
    except Exception as e:
        (run / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        info.paso("PRODUCCION_BLOQUEADA", False, str(e))
        return info.terminar()


def cli():
    from zonas import PERFILES
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("carpeta", type=Path)
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--choques", action="store_true")
    ap.add_argument("--beats")
    audio = ap.add_mutually_exclusive_group()
    audio.add_argument("--sonido", dest="sonido", action="store_true")
    audio.add_argument("--sin-sonido", dest="sonido", action="store_false")
    ap.set_defaults(sonido=None)
    ap.add_argument("--forzar", action="store_true", help="Ejecutar las etapas aunque exista caché válida")
    ap.add_argument("--perfil-zona", choices=list(PERFILES))
    ap.add_argument("--crear-escena", action="store_true")
    ap.add_argument("--salida-escena", type=Path)
    args = ap.parse_args()
    if args.beats and args.final:
        ap.error("--beats solo vale para vista previa")
    if args.choques and args.final:
        ap.error("--choques y --final son modos distintos")
    if args.crear_escena:
        from generar_escena import crear
        try:
            print(f"BORRADOR creado: {crear(args.carpeta, args.salida_escena)}")
            return 0
        except (ValueError, OSError, KeyError) as e:
            ap.error(str(e))
    if args.salida_escena:
        ap.error("--salida-escena requiere --crear-escena")
    return main(args.carpeta, args.final, args.choques, args.beats, args.sonido, args.perfil_zona, args.forzar)


if __name__ == "__main__":
    sys.exit(cli())
