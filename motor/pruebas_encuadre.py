"""Pruebas de encuadre y audio completo. Se ejecutan desde pruebas_motor.py.

Errores que previenen:
- la música de cierre quedó cortada: el audio terminaba 3 s antes que la imagen y una mezcla suelta lo truncó;
- al acercar la cámara, el título salía duplicado (una pieza del HUD se ampliaba);
- la revisión de composición medía en coordenadas de escena aunque la cámara estuviera acercada;
- un inserto excluido con `no_revisar` dejaba de contar en el presupuesto de textos;
- el 2.º paso de un gesto encadenado volvía a la postura previa: anim() tomaba el origen al crearse.
"""
import subprocess
import tempfile
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from manim import Square, Text, VGroup

import choques
from nucleo import FONDO, FUENTE, TIZA, CamaraEstudio, EscenaEstudio
from personajes.demo import Demo
from sonido import PistaSonora, completar_audio, duraciones_video, mezclar


def _cam(zoom=1.0, centro=(0, 0), fijos=()):
    c = CamaraEstudio(pixel_width=270, pixel_height=480, frame_width=9, frame_height=16, background_color=FONDO)
    c.zoom, c.centro, c.fijos = zoom, np.array([centro[0], centro[1], 0.0]), frozenset(id(m) for m in fijos)
    return c


def _dibujar(cam, mobs):
    cam.reset()
    cam.capture_mobjects(mobs)
    return cam.pixel_array.copy()


def _titulo():
    return Text("TÍTULO", font=FUENTE, font_size=40, color=TIZA).move_to([0, 6.8, 0])


def e_hud_no_se_amplia():
    t = _titulo()
    normal = _dibujar(_cam(), [t])
    t2 = _titulo()
    acercado = _dibujar(_cam(1.5, (0, 1), fijos=[t2]), [t2])
    assert np.array_equal(normal, acercado), "El HUD cambia al acercar la cámara"


def e_hud_dentro_de_grupo():
    """El caso del título duplicado: la pieza del HUD está dentro de un grupo; se dibuja UNA vez y sin ampliar."""
    t = _titulo()
    normal = _dibujar(_cam(), [t])
    t2 = _titulo()
    grupo = VGroup(t2)
    acercado = _dibujar(_cam(1.4, (0, .5), fijos=[grupo]), [grupo])
    assert np.array_equal(normal, acercado), "Una pieza del HUD dentro de un grupo se amplía o se duplica"


def e_escena_si_se_amplia():
    def ancho(z):
        img = _dibujar(_cam(z, (0, 0)), [Square(1.0, fill_color=TIZA, fill_opacity=1, stroke_width=0)])
        cols = np.where((img[:, :, :3] > 200).all(axis=2).any(axis=0))[0]
        return cols.max() - cols.min() + 1
    a1, a2 = ancho(1.0), ancho(2.0)
    assert abs(a2 - 2 * a1) <= 2, f"Con zoom 2 el cuadrado mide {a2} px, debería medir ≈{2 * a1}"


def e_zoom_1_igual():
    s = Square(1.0, fill_color=TIZA, fill_opacity=1)
    assert np.array_equal(_dibujar(_cam(), [s]), _dibujar(_cam(1.0, (2, 3)), [s])), "Zoom 1 cambia la imagen"


def e_centro_limitado():
    falsa = SimpleNamespace(_planos=[(0.0, 0.0, 2.0, np.array([4.0, 7.0, 0.0]))], MARCO=EscenaEstudio.MARCO,
                            renderer=SimpleNamespace(time=1.0))
    z, c = EscenaEstudio.estado_camara(falsa)
    assert z == 2.0 and abs(c[0] - 2.25) < 1e-9 and abs(c[1] - 4.0) < 1e-9, \
        f"El cuadro ampliado enseñaría fuera del escenario: centro {c[:2]}"


def _escena(mobs, zoom=1.0, centro=(0, 0)):
    planos = [(0.0, 0.0, zoom, np.array([centro[0], centro[1], 0.0]))]
    esc = SimpleNamespace(mobjects=list(mobs), _hud=[], t=0.0, g=SimpleNamespace(palabras=[], beats=[]),
                          _planos=planos, MARCO=EscenaEstudio.MARCO, renderer=SimpleNamespace(time=1.0))
    esc.estado_camara = lambda t=None: EscenaEstudio.estado_camara(esc, t)
    return esc


def e_choques_en_pantalla():
    """Un texto en y = −3,5 (escena) está dentro de la zona segura con el plano general, pero con zoom 1,5 hacia
    (0, 0) cae en y = −5,25 de pantalla: zona tapada. La revisión tiene que verlo."""
    t = Text("aclaración", font=FUENTE, font_size=26, color=TIZA).move_to([0, -3.5, 0])
    sin = choques.revisar(choques.recoger(_escena([t])))
    con = choques.revisar(choques.recoger(_escena([t], zoom=1.5)))
    assert not [h for h in sin if h["tipo"] == "zona"], "Falsa alarma sin acercamiento"
    assert [h for h in con if h["tipo"] == "zona"], "Con el acercamiento el texto entra en la zona tapada y no avisa"


def e_inserto_cuenta_pero_no_choca():
    actor = Demo()
    panel = VGroup(Text("Hola. ¿Cómo estás?", font=FUENTE, font_size=32, color=TIZA).move_to([0, .9, 0]),
                   Text("borrador", font=FUENTE, font_size=12, color=TIZA).move_to([-1, 2, 0]))
    panel.inserto = True
    hs = choques.revisar(choques.recoger(_escena([actor, panel])))
    assert not [h for h in hs if h["tipo"] == "personaje"], "Un inserto marcado sobre Demo da falsa alarma"
    assert [h for h in hs if h["tipo"] == "pequeno"], "El texto pequeño de un inserto ya no se revisa"
    objetos = choques.recoger(_escena([actor, panel]))
    assert len(choques.bloques(objetos)) == 2, "Los textos del inserto no cuentan en el presupuesto"


class _Guion:
    total = 3.0
    beats = []

    def __getitem__(self, bid):
        raise KeyError(bid)


def _wav(ruta, seg, frec=440.0, amp=0.3):
    sr = 48000
    x = (amp * np.sin(2 * np.pi * frec * np.arange(int(sr * seg)) / sr) * 32767).astype("<i2")
    with wave.open(str(ruta), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr); f.writeframes(x.tobytes())


def e_pista_que_no_cabe():
    with tempfile.TemporaryDirectory() as d:
        w = Path(d) / "musica.wav"
        _wav(w, 1.5)
        PistaSonora(_Guion(), True).archivo(w, 1.0)           # 1,0 + 1,5 = 2,5 ≤ 3,0: cabe
        for activo in (True, False):                          # se valida también sin --sonido
            try:
                PistaSonora(_Guion(), activo).archivo(w, 2.0)
            except ValueError:
                continue
            raise AssertionError("Aceptó una pista que acabaría después del final del video (se cortaría)")


def _mp4(ruta, video_s, audio_s):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=black:s=90x160:r=15:d={video_s}",
                    "-f", "lavfi", "-i", f"sine=frequency=300:duration={audio_s}", "-c:v", "libx264", "-c:a", "aac",
                    "-t", str(video_s), str(ruta)], check=True)


def e_completar_audio():
    with tempfile.TemporaryDirectory() as d:
        v = Path(d) / "corto.mp4"
        _mp4(v, 3, 1.5)
        antes = duraciones_video(v)
        assert antes["audio"] < antes["video"] - 1, "La prueba no reproduce el caso (audio más corto)"
        despues = completar_audio(v)
        assert abs(despues["audio"] - despues["video"]) <= 0.1, f"El audio no llega al final: {despues}"


def e_mezcla_pista_completa():
    """Caso de audio desalineado: la voz acaba en 1,5 s, la imagen en 3 s y la música (1 s) entra en 1,8 s. Tiene que oírse entera."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        v, w, plan, salida = d / "v.mp4", d / "m.wav", d / "plan.json", d / "s.mp4"
        _mp4(v, 3, 1.5)
        _wav(w, 1.0, frec=660, amp=0.2)
        p = PistaSonora(_Guion(), True)
        p.archivo(w, 1.8)
        p.guardar(plan)
        inf = mezclar(v, salida, _Guion(), plan)
        dur = duraciones_video(salida)
        assert dur["audio"] >= 2.8 - 0.05, f"El audio de la mezcla acaba en {dur['audio']:.2f} s"
        raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(salida), "-vn", "-ac", "1", "-ar", "48000",
                                       "-f", "f32le", "-"])
        x = np.frombuffer(raw, dtype="<f4")
        tramo = x[int(2.2 * 48000):int(2.7 * 48000)]
        assert np.sqrt(np.mean(tramo ** 2)) > 0.02, "La música no suena entre 2,2 y 2,7 s (cortada)"
        assert inf["pistas"] and abs(inf["pistas"][0]["hasta"] - 2.8) < 0.01, inf["pistas"]


def e_gesto_encadenado_parte_de_donde_quedo():
    actor=Demo()
    paso1,paso2=actor.anim(pose='explica'),actor.anim(carga=1.)
    for a in (paso1,paso2):
        a.begin(); a.interpolate(1.); a.finish()
    assert np.allclose(actor.mano,Demo.POSES['explica'][0]), 'El segundo paso deshizo la pose'
    assert abs(actor.carga-1.) < 1e-9


PRUEBAS = [(n, f) for n, f in globals().items() if n.startswith("e_") and callable(f)]
