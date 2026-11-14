"""Genera la voz de cada beat del guion y guarda cuándo se pronuncia cada palabra.

Uso:  .venv\\Scripts\\python.exe motor\\tts.py 03-produccion\\<carpeta_del_video>
Lee   <carpeta>/guion.json   (beats con: id, texto, y opcionales voz, rate, pitch)
Crea  <carpeta>/audio/<id>.mp3  y  <carpeta>/audio/tiempos.json

Solo regenera los beats cuyo texto o prosodia cambiaron (guarda una huella en audio/huellas.json).
"""
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import edge_tts
from artefactos import Bloqueo, escribir_json, firma, leer_json, sha256
from contrato import VOCES, PROSODIA, argumentos_voz, errores_palabras, estructura

# VOCES y PROSODIA se reexportan por compatibilidad; su única fuente es contrato.py.


def inspeccionar_audio(ruta, palabras):
    if errores_palabras(palabras) or not Path(ruta).is_file() or Path(ruta).stat().st_size == 0:
        raise ValueError("Audio vacío o palabras/tiempos inválidos")
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                        "stream=duration", "-of", "json", str(ruta)], capture_output=True, text=True, check=True)
    d = float(json.loads(r.stdout)["streams"][0]["duration"])
    if not 0 < d < float("inf") or palabras[-1]["t"] + palabras[-1]["d"] > d + 0.15:
        raise ValueError("La duración del audio no cubre las palabras")
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(ruta), "-f", "null", "-"],
                   capture_output=True, check=True)
    return dict(sha256=sha256(ruta), palabras=firma(palabras), duracion=d)


def cache_valida(ruta, palabras, entrada, huella, cache):
    if entrada != huella or errores_palabras(palabras) or not ruta.is_file() or not ruta.stat().st_size:
        return False
    if isinstance(cache, dict) and cache.get("entrada") == huella:
        try:
            return (cache.get("sha256") == sha256(ruta) and cache.get("palabras") == firma(palabras)
                    and 0 < cache.get("duracion", 0) < float("inf")
                    and palabras[-1]["t"] + palabras[-1]["d"] <= cache["duracion"] + 0.15)
        except (OSError, ValueError, TypeError):
            return False
    return False


async def decir(texto, voz, rate, pitch, destino: Path, intentos=4):
    for n in range(intentos):
        try:
            com = edge_tts.Communicate(texto, voz, rate=rate, pitch=pitch, boundary="WordBoundary")
            palabras, audio = [], bytearray()
            async for ch in com.stream():
                if ch["type"] == "audio":
                    audio += ch["data"]
                elif ch["type"] == "WordBoundary":
                    palabras.append({"w": ch["text"], "t": ch["offset"] / 1e7, "d": ch["duration"] / 1e7})
            if audio and palabras:
                destino.write_bytes(audio)
                return palabras
        except Exception as e:  # el servicio falla a veces con las voces multilingües
            print(f"  reintento {n + 1}: {type(e).__name__}")
        await asyncio.sleep(1.5)
    raise RuntimeError(f"No se pudo generar la voz de: {texto!r}")


async def main(carpeta: Path, solo_comprobar=False):
    carpeta = Path(carpeta)
    original = (carpeta / "guion.json").read_bytes()
    guion = json.loads(original)
    if errores := estructura(guion, completo=False):
        raise ValueError("; ".join(errores))
    out = carpeta / "audio"
    out.mkdir(exist_ok=True)
    with Bloqueo(out / ".tts.lock"):
        return await _preparar(carpeta, guion, original, out, solo_comprobar)


async def _preparar(carpeta, guion, original, out, solo_comprobar):
    f_t, f_h = out / "tiempos.json", out / "huellas.json"
    tiempos, huellas, cache = (leer_json(p, {}) for p in (f_t, f_h, out / "cache.json"))
    tiempos, huellas, cache = (v if isinstance(v, dict) else {} for v in (tiempos, huellas, cache))
    resumen = dict(generados=[], reutilizados=[], adoptados=[], estado="en curso")
    try:
        for b in guion["beats"]:
            bid, args = b["id"], argumentos_voz(b)
            huella = hashlib.md5("|".join(args).encode()).hexdigest()  # conserva huellas históricas
            destino, pal = out / f"{bid}.mp3", tiempos.get(bid)
            if not cache_valida(destino, pal, huellas.get(bid), huella, cache.get(bid)):
                # Una caché histórica se inspecciona una vez; nunca se regenera una voz válida solo por migrar.
                adoptada = False
                if huellas.get(bid) == huella and bid not in cache:
                    try:
                        cache[bid] = dict(inspeccionar_audio(destino, pal), entrada=huella)
                        adoptada = True
                    except (OSError, ValueError, TypeError, KeyError, IndexError, subprocess.SubprocessError):
                        pass
                if adoptada:
                    resumen["adoptados"].append(bid)
                else:
                    if solo_comprobar:
                        raise ValueError(f"{bid}: falta audio válido/vigente; ejecuta producir.py sin --choques para prepararlo")
                    fd, nombre = tempfile.mkstemp(prefix=bid + ".", suffix=".mp3", dir=out)
                    os.close(fd)
                    temporal = Path(nombre)
                    try:
                        pal = await decir(*args, temporal)
                        dato = inspeccionar_audio(temporal, pal)
                        if (carpeta / "guion.json").read_bytes() != original:
                            raise ValueError("El guion cambió durante la generación de voz; no se promueve el audio")
                        os.replace(temporal, destino)
                    finally:
                        temporal.unlink(missing_ok=True)
                    tiempos[bid], huellas[bid] = pal, huella
                    cache[bid] = dict(dato, entrada=huella)
                    # El registro de integridad se confirma al final: una escritura interrumpida no es una caché válida.
                    escribir_json(f_t, tiempos)
                    escribir_json(f_h, huellas)
                    resumen["generados"].append(bid)
                escribir_json(out / "cache.json", cache)
            else:
                resumen["reutilizados"].append(bid)
        if (carpeta / "guion.json").read_bytes() != original:
            raise ValueError("El guion cambió durante la comprobación de voz")
        resumen["estado"] = "ok"
    except Exception as e:
        resumen.update(estado="error", error=str(e))
        raise
    finally:
        escribir_json(out / "resumen-voz.json", resumen)
    total = sum(tiempos[b["id"]][-1]["t"] + tiempos[b["id"]][-1]["d"] + 0.34 for b in guion["beats"])
    print(f"Voz: {len(resumen['generados'])} generados, {len(resumen['reutilizados'])} reutilizados, "
          f"{len(resumen['adoptados'])} adoptados · {total:.1f} s sin colas")
    return resumen


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):        # la consola de Windows (cp1252) mostraba «Duraci�n» (2026-11-13)
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    try:
        asyncio.run(main(Path(sys.argv[1]), solo_comprobar="--comprobar" in sys.argv))
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as e:
        print(f"ERROR VOZ: {e}")
        sys.exit(1)
