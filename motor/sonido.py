"""Sonido original sintetizado y mezcla posterior al render; nunca modifica la voz fuente.

Activar con producir.py --sonido. Plan opcional en sonido.json; también EscenaEstudio.sonido/ambiente.
Pistas de ARCHIVO: música o efectos propios de una producción (WAV/MP3 dentro del proyecto),
con EscenaEstudio.pista(ruta, db, instante) o "pistas" en sonido.json. El motor comprueba que la pista CABE entera en
el video (si no, error: nada de mezclas que corten la música) y la mezcla aquí, nunca con scripts sueltos de ffmpeg.
Los nombres y la procedencia del catálogo son públicos. No contiene música ni recursos descargados.
"""
import hashlib
import json
import math
import subprocess
import wave
from pathlib import Path

import numpy as np
from configuracion import CONFIG

SR = 48000
CATALOGO = {
    "aire": (4.0, "ambiente", "ruido suave filtrado"),
    "lluvia": (4.0, "ambiente", "lluvia estilizada sintetizada"),
    "laboratorio": (4.0, "ambiente", "aire tenue sintetizado"),
    "clic": (0.09, "efecto", "pulsación corta"),
    "pagina": (0.35, "efecto", "roce de papel estilizado"),
    "entrada": (0.38, "efecto", "desplazamiento suave"),
    "deslizar": (0.32, "efecto", "control deslizante"),
    "lupa": (0.22, "efecto", "revelación breve"),
    "rotulo": (0.12, "efecto", "aparición discreta"),
}

# Las semillas fijan la señal, independientemente del nombre usado por un plugin.
_SEMILLAS = {"aire": 2741703412, "lluvia": 1944228948}
_ALIAS = CONFIG.get("sonidos", {}).get("alias", {})
_BASE = frozenset(CATALOGO)
if not isinstance(_ALIAS, dict):
    raise ValueError("Los alias de sonido deben ser un objeto")
for _alias, _destino in _ALIAS.items():
    if not isinstance(_alias, str) or _alias in CATALOGO or not isinstance(_destino, str) or _destino not in _BASE:
        raise ValueError("Alias de sonido inválido o repetido")
    CATALOGO[_alias] = CATALOGO[_destino]


def marcas_animacion(anim, duracion=None):
    """Eventos al EMPEZAR las animaciones, respetando lag y duración de los grupos."""
    resultado = []
    def visitar(a, inicio, factor):
        if getattr(a, "sonido_motor", None):
            resultado.append((a.sonido_motor, inicio))
        tiempos = getattr(a, "anims_with_timings", ())
        if len(tiempos):
            escala = factor * float(a.run_time) / max(float(a.max_end_time), 1e-9)
            for dato in tiempos:
                visitar(dato["anim"], inicio + float(dato["start"])*escala, escala)
    factor = float(duracion) / max(float(anim.run_time), 1e-9) if duracion is not None else 1.0
    visitar(anim, 0, factor)
    return resultado


def ambientes_animacion(anim, duracion=None):
    """Cambios de ambiente en el inicio real de cada animación, incluidos lag y grupos anidados."""
    resultado = []
    def visitar(a, inicio, factor):
        if hasattr(a, "ambiente_motor"):
            resultado.append((a.ambiente_motor, inicio))
        for dato in getattr(a, "anims_with_timings", ()):
            escala = factor * float(a.run_time) / max(float(a.max_end_time), 1e-9)
            visitar(dato["anim"], inicio + float(dato["start"]) * escala, escala)
    factor = float(duracion) / max(float(anim.run_time), 1e-9) if duracion is not None else 1.0
    visitar(anim, 0, factor)
    return resultado


def sintetizar(nombre, sr=SR):
    if nombre not in CATALOGO:
        raise ValueError(f"Sonido desconocido: {nombre}. Disponibles: {', '.join(CATALOGO)}")
    nombre = _ALIAS.get(nombre, nombre)
    dur, tipo, _ = CATALOGO[nombre]
    n = round(dur * sr)
    t = np.arange(n) / sr
    semilla = _SEMILLAS.get(nombre, int.from_bytes(hashlib.sha256(nombre.encode()).digest()[:4], "big"))
    rng = np.random.default_rng(semilla)
    ruido = rng.normal(size=n)
    freq = np.fft.rfftfreq(n, 1 / sr)
    corte = 650 if nombre == "aire" else 2200 if nombre == "lluvia" else 1400
    filtro = np.minimum(freq / 90, 1) / (1 + (freq / corte) ** 4)
    suave = np.fft.irfft(np.fft.rfft(ruido) * filtro, n)
    if tipo == "ambiente":
        x = suave
    elif nombre == "clic":
        x = (0.6 * suave + np.sin(2 * np.pi * 950 * t)) * np.exp(-t * 70)
    elif nombre in ("pagina", "entrada", "deslizar"):
        x = suave * np.sin(np.pi * t / dur) ** 2
    else:
        x = np.sin(2 * np.pi * (620 * t + 400 * t * t)) * np.exp(-t * 20)
    x = x / max(float(np.sqrt(np.mean(x * x))), 1e-8)
    if tipo == "ambiente":
        # El ruido filtrado por FFT es periódico: el bucle empalma sin costura. Una rampa aquí dejaba un hueco de
        # ~16 ms cada 4 s al repetirlo. Los fundidos de entrada/salida del ambiente los pone capas().
        return x.astype(np.float32)
    # Rampa incluso en los clics: sin discontinuidades digitales.
    r = min(round(sr * 0.008), n // 4)
    x[:r] *= np.linspace(0, 1, r)
    x[-r:] *= np.linspace(1, 0, r)
    return x.astype(np.float32)


def _marca(g, valor):
    if isinstance(valor, (int, float)):
        t = float(valor)
    elif isinstance(valor, dict):
        bid = valor["beat"]
        t = g.t_palabra(bid, valor["palabra"], int(valor.get("n", 0))) if "palabra" in valor else g[bid][valor.get("borde", "ini")]
        t += float(valor.get("desfase", 0))
    else:
        raise ValueError("La marca de sonido debe ser segundos o {beat, palabra/n/borde}.")
    if not math.isfinite(t) or t < 0 or t > g.total:
        raise ValueError(f"Marca de sonido fuera del guion: {t}")
    return t


class PistaSonora:
    def __init__(self, g, activo=False):
        self.g, self.activo = g, activo
        self.efectos, self.ambientes, self.pistas, self._claves = [], [], [], set()
        self._ambiente_abierto = None

    CERCA = 0.12      # el mismo efecto a menos de esto de otro igual es la misma marca (automática + escrita)

    def efecto(self, nombre, t, db=-22, clave=None):
        if not self.activo:
            return
        self._validar(nombre, db, "efecto")
        t = _marca(self.g, t)
        if clave is not None:
            if clave in self._claves:
                return
            self._claves.add(clave)
        elif any(e["nombre"] == nombre and abs(e["t"] - t) < self.CERCA for e in self.efectos):
            return
        self.efectos.append(dict(nombre=nombre, t=t, db=float(db)))

    def callar(self, t):
        """Corta en `t` el ambiente abierto (cambio a un escenario sin ambiente)."""
        if not self.activo:
            return
        t = _marca(self.g, t)
        for a in list(self.ambientes):
            if a["desde"] <= t < a["hasta"]:
                a["hasta"] = t
                if a["hasta"] <= a["desde"]:
                    self.ambientes.remove(a)
        if self._ambiente_abierto is not None and self._ambiente_abierto["desde"] <= t:
            self._ambiente_abierto = None

    def ambiente(self, nombre, desde, hasta=None, db=-30):
        if not self.activo:
            return
        self._validar(nombre, db, "ambiente")
        a, b = _marca(self.g, desde), _marca(self.g, self.g.total if hasta is None else hasta)
        if b <= a:
            raise ValueError("Un ambiente debe terminar después de empezar.")
        self.callar(a)
        dato = dict(nombre=nombre, desde=a, hasta=b, db=float(db))
        if dato not in self.ambientes:
            self.ambientes.append(dato)
            if hasta is None:
                self._ambiente_abierto = dato

    def archivo(self, ruta, t, db=0.0, atenuar=True):
        """Pista de archivo propia (música, efecto grabado). `db` = ganancia sobre el archivo tal cual (0 = sin tocar).
        Se valida SIEMPRE (también sin --sonido): si el archivo no existe o no cabe entero antes del final del guion,
        error. Así una música de cierre no puede quedar cortada."""
        ruta = Path(ruta).resolve()
        if not isinstance(atenuar, bool):
            raise ValueError("atenuar debe ser true o false")
        if not ruta.exists():
            raise ValueError(f"No existe la pista {ruta}")
        if not math.isfinite(float(db)) or not -40 <= float(db) <= 12:
            raise ValueError("Ganancia de pista fuera de rango: entre −40 y +12 dB sobre el archivo.")
        t = _marca(self.g, t)
        dur = duracion_audio(ruta)
        if t + dur > self.g.total + 0.02:
            raise ValueError(f"La pista {ruta.name} ({dur:.2f} s) empieza en {t:.2f} s y acabaría en {t + dur:.2f} s, "
                             f"después del final del guion ({self.g.total:.2f} s): se cortaría. Alarga la cola del último beat.")
        if not self.activo:
            return
        dato = dict(archivo=str(ruta), t=t, db=float(db), dur=dur, atenuar=atenuar)
        if dato not in self.pistas:
            self.pistas.append(dato)

    @staticmethod
    def _validar(nombre, db, tipo):
        if nombre not in CATALOGO or CATALOGO[nombre][1] != tipo:
            raise ValueError(f"{nombre!r} no es un {tipo} del catálogo.")
        if not math.isfinite(float(db)) or not -60 <= float(db) <= -12:
            raise ValueError("Ganancia relativa fuera de rango: usar entre −60 y −12 dB respecto a la voz.")

    def cargar(self, ruta):
        if not Path(ruta).exists():
            return
        plan = json.loads(Path(ruta).read_text(encoding="utf-8-sig"))
        if not isinstance(plan, dict) or any(not isinstance(plan.get(k, []), list) for k in ("ambientes", "efectos", "pistas")):
            raise ValueError("sonido.json debe contener listas de ambientes, efectos y pistas")
        for a in sorted(plan.get("ambientes", []), key=lambda a: _marca(self.g, a["desde"])):
            self.ambiente(a["nombre"], a["desde"], a.get("hasta"), a.get("db", -30))
        for e in plan.get("efectos", []):
            self.efecto(e["nombre"], e["en"], e.get("db", -22), e.get("clave"))
        for p in plan.get("pistas", []):
            self.archivo(Path(ruta).parent / p["archivo"], p["en"], p.get("db", 0.0), p.get("atenuar", True))

    def guardar(self, ruta):
        if not self.activo:
            return
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        datos = dict(ambientes=self.ambientes, efectos=self.efectos, pistas=self.pistas,
                     procedencia="Síntesis original determinista de motor/sonido.py; las pistas de archivo son propias de "
                                 "la producción y declaradas en ella (sin música de terceros)",
                     catalogo={k: dict(duracion=v[0], tipo=v[1], descripcion=v[2]) for k, v in CATALOGO.items()})
        Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def duracion_audio(ruta):
    """Duración en segundos del primer flujo de audio de un archivo (ffprobe)."""
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration",
                                   "-of", "csv=p=0", str(ruta)], text=True).strip()
    return float(out)


def leer_audio(ruta, sr=SR):
    """Audio mono float32 a `sr` Hz."""
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(ruta), "-vn", "-ar", str(sr), "-ac", "1", "-f", "f32le", "pipe:1"])
    return np.frombuffer(raw, dtype="<f4").copy()


def duraciones_video(ruta):
    """{"video": s, "audio": s} de los flujos de un MP4; la duración del contenedor puede ocultar un audio cortado."""
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "csv=p=0",
                                   str(ruta)], text=True)
    d = {}
    for linea in out.split():
        tipo, _, seg = linea.partition(",")
        if seg and seg != "N/A" and tipo not in d:
            d[tipo] = float(seg)
    return d


def completar_audio(video, tolerancia=0.05):
    """Si el audio de `video` termina antes que la imagen, lo rellena con silencio hasta el final (sin tocar la imagen
    ni recodificar el video). Devuelve las duraciones finales. Manim deja el audio donde acaba la última voz."""
    video = Path(video)
    d = duraciones_video(video)
    if "audio" in d and "video" in d and d["audio"] < d["video"] - tolerancia:
        tmp = video.with_name(video.stem + ".completo.mp4")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy",
                        "-af", f"apad=whole_dur={d['video']:.3f}", "-c:a", "aac", "-b:a", "192k", "-t", f"{d['video']:.3f}",
                        "-movflags", "+faststart", str(tmp)], check=True)
        tmp.replace(video)
        d = duraciones_video(video)
    return d


def envolvente_voz(g, n, sr=SR):
    """Atenuación con ataque anticipado y salida suave; las colas no se confunden con voz."""
    env = np.ones(n, np.float32)
    for b in g.beats:
        a, z = b["palabras"][0]["t"], b["palabras"][-1]["t"] + b["palabras"][-1]["d"]
        i, j = max(0, round(a * sr)), min(n, round(z * sr))
        if i >= n or j <= 0:
            continue
        env[i:j] = np.minimum(env[i:j], 0.38)
        lo, hi = max(0, i - round(0.08 * sr)), min(n, j + round(0.20 * sr))
        env[lo:i] = np.minimum(env[lo:i], np.linspace(1, 0.38, i - lo))
        env[j:hi] = np.minimum(env[j:hi], np.linspace(0.38, 1, hi - j))
    return env


def capas(g, n, eventos, sr=SR):
    fondo, fx = np.zeros(n, np.float32), np.zeros(n, np.float32)
    for a in eventos.get("ambientes", []):
        i, j = max(0, round(a["desde"] * sr)), min(n, round(a["hasta"] * sr))
        if j <= i:
            continue
        onda = sintetizar(a["nombre"], sr)
        x = np.resize(onda, j - i) * 10 ** (a["db"] / 20)
        r = min(round(sr * 0.35), len(x) // 2)
        x[:r] *= np.linspace(0, 1, r)
        x[-r:] *= np.linspace(1, 0, r)
        fondo[i:j] += x
    for e in eventos.get("efectos", []):
        i = round(e["t"] * sr)
        onda = sintetizar(e["nombre"], sr) * 10 ** (e["db"] / 20)
        z = min(len(onda), n - i)
        if i >= 0 and z > 0:
            fx[i:i + z] += onda[:z]
    return (fondo + fx) * envolvente_voz(g, n, sr)


def mezclar(video, destino, g, eventos_ruta, desde=0.0):
    """Mezcla sobre una copia: la entrada y la voz de sus beats permanecen intactas."""
    video, destino = Path(video), Path(destino)
    if video.resolve() == destino.resolve():
        raise ValueError("La mezcla debe tener un archivo de salida distinto del video fuente.")
    datos = json.loads(Path(eventos_ruta).read_text(encoding="utf-8"))
    voz_raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ar", str(SR), "-ac", "1", "-f", "f32le", "pipe:1"])
    voz = np.frombuffer(voz_raw, dtype="<f4").copy()
    # Una cola visual puede continuar después del último paquete de voz. No recortarla con -shortest.
    meta = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                              "-show_entries", "stream=duration", "-of", "json", str(video)]))
    duracion = float(meta["streams"][0]["duration"])
    if not math.isfinite(duracion) or duracion <= 0:
        raise ValueError("El video no tiene una duración válida para la mezcla.")
    n_video = round(duracion * SR)
    voz = np.pad(voz, (0, max(0, n_video-len(voz))))[:n_video]
    offset = round(desde * SR)
    extra = capas(g, len(voz) + offset, datos)[offset:]
    activos = voz[np.abs(voz) > 0.008]
    rms = float(np.sqrt(np.mean(activos * activos))) if len(activos) else 0.08
    # Además del RMS relativo, limitar el pico del acompañamiento: transitorios bajo la voz.
    extra *= rms
    pico_voz = max(float(np.max(np.abs(voz))), 1e-6)
    pico_extra = float(np.max(np.abs(extra)))
    if pico_extra > pico_voz * 0.12:
        extra *= pico_voz * 0.12 / pico_extra
    # Pistas de archivo: a su nivel (db sobre el archivo), sin el límite del 12 % de los sintetizados. Si una no cabe
    # entera, error: nunca se corta una música en silencio.
    for p in datos.get("pistas", []):
        x = leer_audio(p["archivo"]) * 10 ** (p["db"] / 20)
        i = round((p["t"] - desde) * SR)
        if i + len(x) > len(voz) + round(0.02 * SR):
            raise ValueError(f"La pista {Path(p['archivo']).name} acaba en {(i + len(x)) / SR + desde:.2f} s y el video en "
                             f"{len(voz) / SR + desde:.2f} s: se cortaría.")
        lo, hi = max(i, 0), min(i + len(x), len(voz))
        if hi > lo:
            segmento = x[lo - i:hi - i].copy()
            if p.get("atenuar", True):
                env = envolvente_voz(g, len(voz))[lo:hi]
                factor = min(1.0, pico_voz * 0.12 / max(float(np.max(np.abs(segmento))), 1e-9))
                # Sin habla conserva su nivel; bajo voz aplica un límite relativo con ataque/salida suaves.
                segmento *= 1 - (1 - factor) * np.clip((1 - env) / 0.62, 0, 1)
            extra[lo:hi] += segmento
    mezcla = voz + extra
    ganancia = min(1.0, 0.89 / max(float(np.max(np.abs(mezcla))), 1e-6))
    mezcla *= ganancia
    wav = destino.with_suffix(".mezcla.wav")
    temporal = destino.with_name(destino.stem + ".temporal.mp4")
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR)
        f.writeframes((mezcla * 32767).astype("<i2").tobytes())
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(wav),
                        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", "-t", f"{duracion:.6f}", str(temporal)], check=True)
        temporal.replace(destino)
    finally:
        wav.unlink(missing_ok=True)
        temporal.unlink(missing_ok=True)
    informe = dict(fuente=str(video), salida=str(destino), rms_voz=rms,
                   pico_acompanamiento=float(np.max(np.abs(extra))), pico_voz=pico_voz,
                   ganancia_final=ganancia, muestras=len(voz), frecuencia=SR,
                   limite_pico_relativo=0.12, atenuacion_durante_voz=0.38,
                   pistas=[dict(archivo=Path(p["archivo"]).name, desde=p["t"], hasta=p["t"] + p["dur"], db=p["db"])
                           for p in datos.get("pistas", [])])
    destino.with_suffix(".sonido.json").write_text(json.dumps(informe, indent=2) + "\n", encoding="utf-8")
    return informe
