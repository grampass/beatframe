"""Casos positivos y negativos de las cuatro mejoras de Codex. Se ejecutan desde pruebas_motor.py."""
import ast
import json
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image
from manim import Text, Circle, Wait, AnimationGroup, Scene

import choques
from contraste import estimar, razon
from generar_escena import crear
from personajes.demo import Demo
from sonido import PistaSonora, sintetizar, envolvente_voz, mezclar, marcas_animacion
from zonas import contiene, normalizar, perfil


class GuionPrueba:
    total = 3.0
    beats = [dict(id="b1", palabras=[dict(t=1.0, d=0.6)])]
    def __getitem__(self, bid):
        if bid != "b1":
            raise KeyError(bid)
        return dict(ini=1.0, fin=2.0)
    def t_palabra(self, bid, palabra, n=0):
        if (bid, palabra, n) != ("b1", "mira", 0):
            raise KeyError((bid, palabra, n))
        return 1.25


def audio_eventos():
    p = PistaSonora(GuionPrueba(), True)
    p.efecto("clic", {"beat":"b1", "palabra":"mira"})
    p.efecto("clic", 1.25)
    assert len(p.efectos) == 1 and p.efectos[0]["t"] == 1.25
    p.ambiente("aire", 0)
    p.ambiente("laboratorio", 1)
    assert p.ambientes[0]["hasta"] == 1 and p.ambientes[1]["hasta"] == 3
    try:
        p.efecto("clic", 4)
    except ValueError:
        return
    raise AssertionError("Aceptó un efecto fuera del guion")


def audio_apagado():
    p = PistaSonora(GuionPrueba(), False)
    p.efecto("clic", 1)
    p.ambiente("aire", 0)
    assert not p.efectos and not p.ambientes


def audio_grupos():
    a, b = Wait(1), Wait(1)
    a.sonido_motor, b.sonido_motor = "clic", "pagina"
    grupo = AnimationGroup(a, b, lag_ratio=1, run_time=3)
    assert marcas_animacion(grupo) == [("clic",0), ("pagina",1.5)]
    assert marcas_animacion(grupo, 4) == [("clic",0), ("pagina",2)]


def audio_ducking():
    e = envolvente_voz(GuionPrueba(), 300, sr=100)
    assert e[20] == 1 and abs(e[120]-0.38) < 1e-6 and e[220] == 1
    assert e[94] < e[92] and e[175] > e[165]
    for nombre in ("clic", "pagina", "aire"):
        x = sintetizar(nombre)
        assert np.all(np.isfinite(x)) and np.array_equal(x, sintetizar(nombre))
        if nombre != "aire":       # los efectos empiezan y acaban en 0; el ambiente es un bucle sin rampa
            assert abs(x[0]) < 1e-7 and abs(x[-1]) < 1e-7


def _rms_corto(x, sr=48000, ms=5):
    w = max(1, int(sr * ms / 1000))
    return np.sqrt(np.convolve(x * x, np.ones(w) / w, "same"))


def audio_bucle_sin_costura():
    """un ambiente se repite cada 4 s; en el empalme no puede caer a cero."""
    from sonido import capas, CATALOGO
    for nombre, (dur, tipo, _) in CATALOGO.items():
        if tipo != "ambiente":
            continue
        x = sintetizar(nombre)
        y = np.tile(x, 3)
        rms = _rms_corto(y)
        k = len(x)
        zona = rms[k - 480:k + 480]                     # ±10 ms alrededor del empalme
        assert zona.min() > 0.35 * np.median(rms), f"{nombre}: el bucle cae a {zona.min():.3f} en el empalme (mediana {np.median(rms):.3f})"
    # y dentro de la mezcla real: un ambiente de 9 s no tiene huecos en 4 s ni en 8 s
    class G:
        total, beats = 9.0, []
    sr = 48000
    fondo = capas(G(), 9 * sr, dict(ambientes=[dict(nombre="aire", desde=0, hasta=9, db=-30)]))
    rms = _rms_corto(fondo)
    for seg in (4, 8):
        zona = rms[seg * sr - 480:seg * sr + 480]
        assert zona.min() > 0.35 * np.median(rms[sr:8 * sr]), f"hueco en el ambiente mezclado en {seg} s"


def audio_efecto_tardio_no_detiene():
    """un efecto automático que cae después del guion se omite con aviso; no detiene el render."""
    from nucleo import EscenaEstudio
    from manim import Scene
    from unittest.mock import patch
    p = PistaSonora(GuionPrueba(), True)
    falsa = SimpleNamespace(_sonora=p, renderer=SimpleNamespace(time=3.4))
    EscenaEstudio.sonido(falsa, "clic")                     # GuionPrueba.total = 3.0
    assert not p.efectos, "un efecto posterior al guion no debe mezclarse"
    try:                                                    # la marca escrita a mano en sonido.json sigue siendo estricta
        p.efecto("clic", 4)
    except ValueError:
        return
    raise AssertionError("una marca escrita fuera del guion debe seguir avisando con ValueError")


def audio_duplicado_cercano():
    """la marca automática y la escrita a mano del mismo sonido, a pocos ms, suenan una vez."""
    p = PistaSonora(GuionPrueba(), True)
    p.efecto("clic", 1.25)
    p.efecto("clic", 1.28)
    p.efecto("lupa", 1.26)                                  # otro sonido en el mismo instante sí suena
    p.efecto("clic", 1.6)
    assert [e["nombre"] for e in p.efectos] == ["clic", "lupa", "clic"], p.efectos





def audio_ambiente_con_transicion():
    """enfocar/desenfocar pueden cortar y reanudar el ambiente en el mismo instante que la imagen."""
    from nucleo import EscenaEstudio

    class Escena(EscenaEstudio):
        def setup(self):
            pass
    e = Escena()
    e.setup()
    e._sonora = PistaSonora(GuionPrueba(), True)
    e.renderer.time = 0.0
    e.ambiente("aire")
    e.renderer.time = 1.0
    corte = e.enfocar_anim(ambiente=None)
    assert e._sonora.ambientes[0]["hasta"] == 3.0, "Construir la animación no debe cortar el ambiente"
    with patch.object(Scene, "play"):
        e.play(corte)
    e.renderer.time = 2.0
    vuelta = e.desenfocar_anim(ambiente="aire")
    with patch.object(Scene, "play"):
        e.play(vuelta)
    a = e._sonora.ambientes
    assert [(x["nombre"], x["desde"], x["hasta"]) for x in a] == [("aire", 0.0, 1.0), ("aire", 2.0, 3.0)], a
    e.renderer.time = 2.5
    e.enfocar_anim()                                         # sin argumento: el sonido no cambia
    assert len(e._sonora.ambientes) == 2 and e._sonora.ambientes[1]["hasta"] == 3.0


def audio_exportacion():
    with tempfile.TemporaryDirectory(prefix="motor-audio-") as d:
        p = Path(d).resolve()
        assert p.parent == Path(tempfile.gettempdir()).resolve()
        original, salida, plan = p/"original.mp4", p/"sonido.mp4", p/"plan.json"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=black:s=90x160:r=15:d=3",
                        "-f", "lavfi", "-i", "sine=frequency=300:duration=1", "-c:v", "libx264", "-c:a", "aac", "-t", "3", str(original)], check=True)
        pson = PistaSonora(GuionPrueba(), True)
        pson.ambiente("aire", 0)
        pson.efecto("clic", 1.25)
        pson.guardar(plan)
        antes = original.read_bytes()
        resultado = mezclar(original, salida, GuionPrueba(), plan)
        assert resultado["muestras"] == 3*48000, "La mezcla recortó la cola visual sin voz"
        assert original.read_bytes() == antes
        assert resultado["pico_acompanamiento"] <= resultado["pico_voz"]*0.12001
        def video_hash(f):
            return subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(f), "-map", "0:v:0", "-c", "copy", "-f", "hash", "-"])
        assert video_hash(original) == video_hash(salida), "La mezcla cambió el stream de imagen"
        primero = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(salida), "-vn", "-f", "f32le", "-"])
        mezclar(original, salida, GuionPrueba(), plan)
        segundo = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(salida), "-vn", "-f", "f32le", "-"])
        assert primero == segundo, "Reejecutar acumula o modifica efectos"
        try:
            mezclar(original, original, GuionPrueba(), plan)
        except ValueError:
            return
        raise AssertionError("Aceptó sobrescribir el video fuente")


def zonas_geometria():
    assert np.allclose(normalizar([-4.5,-8,4.5,8]), [0,0,1,1])
    assert contiene([0.1,0.1,0.85,0.8], "legado")
    assert not contiene([0.1,0.1,0.86,0.8], "legado")
    assert not contiene([0.95,0.95,0.951,0.951], "youtube", tolerancia=0.002)
    assert perfil("youtube")["evidencia"] == "estimacion_proyecto"


def zonas_escalon():
    assert contiene([0.2,0.42,0.70,0.48], "tiktok-anuncio")
    assert not contiene([0.2,0.42,0.76,0.48], "tiktok-anuncio")
    assert not contiene([0.2,0.2,0.7,0.8], "tiktok-anuncio")


def zonas_hud():
    t = Text("TITULO", font_size=24).move_to([0,7,0])
    objetos = choques.recoger(SimpleNamespace(mobjects=[t], _hud=[t]))
    assert not any(h["tipo"] == "zona" for h in choques.revisar(objetos))
    assert any(h["tipo"] == "zona" for h in choques.revisar(objetos, perfil="youtube"))


def _guion_esqueleto():
    return dict(beats=[dict(id="b1", texto="Mira, mira el vaso.", claves={"mira":"ambar"},
                           visual="Aparece el vaso.\nDespués Demo lo señala.", composicion="laboratorio")])


def esqueleto_seguro():
    with tempfile.TemporaryDirectory(prefix="motor-guion-") as d:
        p = Path(d).resolve(); assert p.parent == Path(tempfile.gettempdir()).resolve()
        (p/"guion.json").write_text(json.dumps(_guion_esqueleto()), encoding="utf-8")
        f = crear(p)
        fuente = f.read_text(encoding="utf-8")
        ast.parse(fuente)
        assert "n=0" in fuente and "se repite" in fuente and "NotImplementedError" in fuente
        assert "self.fin_beat('b1')" in fuente and "# Después Demo" not in fuente
        assert "# Visual: Después Demo" in fuente
        antes = f.read_bytes()
        try:
            crear(p)
        except FileExistsError:
            assert f.read_bytes() == antes
            return
        raise AssertionError("Sobrescribió una escena existente")


def esqueleto_palabra_ausente():
    with tempfile.TemporaryDirectory(prefix="motor-clave-") as d:
        p=Path(d).resolve(); assert p.parent == Path(tempfile.gettempdir()).resolve()
        g = _guion_esqueleto();g["beats"][0]["claves"] = {"ausente":"ambar"}
        (p/"guion.json").write_text(json.dumps(g), encoding="utf-8")
        try:
            crear(p)
        except ValueError:
            assert not (p/"escena.py").exists()
            return
        raise AssertionError("Aceptó una marca que no existe en la voz")


def brazo_detectado():
    p = Demo([0,0], escala=0.6, pose="explica")
    mano = p.punto(*p.mano)
    t = Text("X", font_size=20).move_to(mano)
    assert t.get_left()[0] > p.caja_cuerpo()[2], "El caso debe estar fuera del cuerpo"
    objetos = choques.recoger(SimpleNamespace(mobjects=[p,t],_hud=[]))
    assert any(h["tipo"] == "personaje" for h in choques.revisar(objetos)), "No detectó texto bajo la mano"


def brazo_hueco_libre():
    p = Demo([0,0], escala=0.6, pose="explica")
    t = Text("X", font_size=20).move_to([1.0,-0.6,0])
    objetos = choques.recoger(SimpleNamespace(mobjects=[p,t],_hud=[]))
    assert not any(h["tipo"] == "personaje" for h in choques.revisar(objetos)), "Avisó sobre espacio vacío bajo el brazo"


def senalar_elige_lado():
    p = Demo([0,-2], escala=0.45)
    a = p.senalar(Circle(0.2).move_to([0,0,0]), pose="auto", ocupados=[[0.3,-3,3.1,4]])
    assert p.ultima_senal["lado"] == "izquierda", "Eligió el lado ocupado"
    a.begin();a.interpolate(1);a.finish()
    assert p.caja_cuerpo()[2] < -0.2


def senalar_elige_altura():
    elegidas = []
    for altura in (3.5,-1.0,-2.5):
        p = Demo([0,-2], escala=0.6)
        p.senalar(Circle(0.25).move_to([2.5,altura,0]), pose="auto")
        elegidas.append(p.ultima_senal["pose"])
    assert elegidas[0] == "senala" and elegidas[1] == "explica" and elegidas[2] in ("jala","mira_abajo"), elegidas


def contraste_positivo_negativo():
    t = dict(nombre="blanco", caja=[-1,-1,1,1], color=[255,255,255])
    assert abs(razon([255,255,255],[0,0,0])-21) < 1e-6
    assert estimar(Image.new("RGB", (90,160), "white"), t)["razon"] == 1
    assert estimar(Image.new("RGB", (90,160), "black"), t) is None
    t.update(contorno_ancho=3, contorno_opacidad=1, contorno_color=[0,0,0])
    assert estimar(Image.new("RGB", (90,160), "white"), t) is None


PRUEBAS = [
    ("sonido · marcas exactas, deduplicación y cambio de ambiente", audio_eventos),
    ("sonido · desactivado conserva solo voz", audio_apagado),
    ("sonido · grupos respetan retraso y duración real", audio_grupos),
    ("sonido · baja bajo voz, rampas y síntesis determinista", audio_ducking),
    ("sonido · exportación conserva imagen/fuente, limita nivel y no acumula", audio_exportacion),
    ("sonido · el ambiente en bucle no cae en los empalmes", audio_bucle_sin_costura),
    ("sonido · enfocar/desenfocar cortan y reanudan el ambiente", audio_ambiente_con_transicion),
    ("sonido · el mismo efecto a pocos ms suena una vez", audio_duplicado_cercano),
    ("sonido · efecto automático tras el guion: aviso, no error", audio_efecto_tardio_no_detiene),
    ("zonas · normalización, margen y procedencia", zonas_geometria),
    ("zonas · unión escalonada de plantilla oficial", zonas_escalon),
    ("zonas · el perfil explícito también revisa HUD", zonas_hud),
    ("esqueleto · sintaxis, marcas repetidas y no sobrescritura", esqueleto_seguro),
    ("esqueleto · clave inexistente rechazada sin crear archivo", esqueleto_palabra_ausente),
    ("composición · texto bajo mano fuera de la caja del cuerpo", brazo_detectado),
    ("composición · espacio vacío bajo brazo no da alarma", brazo_hueco_libre),
    ("señalar · pose auto evita el lado ocupado", senalar_elige_lado),
    ("señalar · el gesto cambia para objetivo alto, medio y bajo", senalar_elige_altura),
    ("contraste · fondo raster claro/oscuro y contorno", contraste_positivo_negativo),
]
