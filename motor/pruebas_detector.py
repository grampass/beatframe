"""Casos límite del detector y del relevo de aclaraciones, sin diseños concretos."""
from types import SimpleNamespace

import numpy as np
from manim import BLUE, RED, Scene, Text, Write

import choques
from nucleo import CamaraEstudio, EscenaEstudio, FONDO, FUENTE, TIZA, nota
from plano import Plano
from sonido import marcas_animacion


def _escena(*mobs):
    return SimpleNamespace(mobjects=list(mobs), _hud=[], t=0)


def d_escritura_color_efectivo():
    t = nota("Una ley", TIZA, 36)
    a = Write(t)
    a.begin()
    for alfa in (.25, .5, .75, 1):
        a.interpolate(alfa)
        objetos = choques.recoger(_escena(t))
        assert objetos, alfa
        for o in objetos:
            assert len(o["color"]) == 3 and np.isfinite(o["color"]).all(), o


def d_contorno_multicolor_y_contorno_invisible():
    t = Text("Color", font=FUENTE, font_size=24)
    for ancho, opacidad in ((0, 0), (6, 1)):
        t.set_stroke(color=[RED, BLUE], width=ancho, opacity=opacidad, background=True)
        o = choques.recoger(_escena(t))[0]
        assert o["contorno_ancho"] == ancho and o["contorno_opacidad"] == opacidad, o
        if ancho:
            assert np.allclose(o["contorno_color"], RED.to_rgb()*255), o
        else:
            assert "contorno_color" not in o


def d_aparcados_y_recortes_visibles():
    for pos in ((-5.5, 0, 0), (5.5, 0, 0), (0, 8.5, 0), (0, -8.5, 0)):
        t = Text("Fuera", font=FUENTE, font_size=24).move_to(pos)
        assert not choques.recoger(_escena(t)), pos
    for pos in ((-4.5, 0, 0), (0, 8, 0)):
        t = Text("Borde", font=FUENTE, font_size=24).move_to(pos)
        objetos = choques.recoger(_escena(t))
        assert objetos and any(h["tipo"] == "fuera" for h in choques.revisar(objetos)), pos


def d_trazo_visible_alcanza_el_cuadro():
    t = Text("Borde", font=FUENTE, font_size=24).set_stroke(TIZA, width=100, background=True)
    t.move_to([-4.5-t.width/2-.15, 0, 0])
    assert choques._caja(t)[2] < -4.5
    assert choques.recoger(_escena(t)), "Se descartó un trazo que entra en pantalla"
    kw = dict(pixel_width=270, pixel_height=480, frame_width=9, frame_height=16, background_color=FONDO)
    cam, vacia = CamaraEstudio(**kw), CamaraEstudio(**kw)
    cam.capture_mobjects([t])
    assert not np.array_equal(cam.pixel_array, vacia.pixel_array)


def d_acercamiento_respeta_objetos_fijos():
    t = Text("Fijo", font=FUENTE, font_size=24).move_to([-4, 0, 0])
    s = _escena(t)
    s.estado_camara = lambda: (2.0, np.zeros(3))
    assert not choques.recoger(s)
    t.fijo = True
    assert choques.recoger(s), "El HUD fijo recibió el zoom de la escena"


def _iniciar(s, anims):
    s.add_mobjects_from_animations(anims)
    for a in anims:
        a._setup_scene(s)
        a.begin()


def _terminar(s, anims):
    for a in anims:
        a.finish()
        a.clean_up_from_scene(s)


def d_relevo_unico_tiempo_sonido_y_limpieza():
    s = Scene()
    s._hud, s._rotulo, s._rotulo_hasta, s.plano = [], None, None, Plano("laboratorio")
    primera = EscenaEstudio.rotulo_anim(s, "Anterior")
    _iniciar(s, primera)
    _terminar(s, primera)
    anterior = s._rotulo
    relevo = EscenaEstudio.rotulo_anim(s, "Siguiente", hasta="b2")
    assert max(a.run_time for a in relevo) == 1.0, "Cambió la duración implícita"
    assert [e for a in relevo for e in marcas_animacion(a, .4)] == [("rotulo", .2)]
    _iniciar(s, relevo)
    for alfa in np.linspace(0, 1, 41):
        for a in relevo:
            a.interpolate(float(alfa))
        objetos = choques.recoger(s)
        assert len(choques.bloques(objetos)) <= 1, (alfa, [o["nombre"] for o in objetos])
        assert not [h for h in choques.revisar(objetos) if h["tipo"] == "solape"], alfa
    _terminar(s, relevo)
    assert anterior not in s.get_mobject_family_members()
    assert s._rotulo in s.get_mobject_family_members() and s._rotulo_hasta == "b2"
    quitar = EscenaEstudio.rotulo_anim(s)
    _iniciar(s, quitar)
    _terminar(s, quitar)
    assert s._rotulo is None and not choques.recoger(s)


def d_muestras_guardan_tamano_y_visibilidad():
    t = Text("Medible", font=FUENTE, font_size=24)
    r = choques.Registro()
    r.foto(_escena(t), "b1")
    o = r.muestras[-1]["objetos"][0]
    assert abs(o["tam"]-24) < 1e-5 and o["vis"] == 1.0, o


PRUEBAS = [(n, f) for n, f in globals().items() if n.startswith("d_") and callable(f)]
