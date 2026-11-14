"""Pruebas de exactitud del motor: comparan lo que dibuja CamaraEstudio con lo que dibuja la cámara de Manim.

Uso:  .venv\\Scripts\\python.exe motor\\pruebas_motor.py
Termina con «TODO BIEN» (código 0) o con la lista de pruebas fallidas (código 1). Tarda unos segundos.
Obligatorio después de tocar cualquier archivo de motor/, junto con regresion.py (Guía 5 §5).

Cada prueba dibuja a 270x480 con encuadre 9x16. CamaraEstudio puede saltarse trabajo (no dibujar lo que no se ve,
reutilizar fondos), pero el resultado tiene que ser idéntico al de Camera píxel a píxel.
"""

import sys
import os
if __name__ == '__main__':
    os.environ['MOTOR_CONFIG'] = '-'
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import logging                                        # noqa: E402

import numpy as np                                    # noqa: E402
from manim import Camera, Circle, ImageMobject, Line, Square, VMobject  # noqa: E402

from nucleo import AMBAR, CALIENTE, FONDO, TIZA, CamaraEstudio  # noqa: E402

logging.getLogger("manim").setLevel(logging.ERROR)    # sin los avisos de LaTeX al crear números

ANCHO, ALTO = 270, 480


def camara(clase):
    return clase(pixel_width=ANCHO, pixel_height=ALTO, frame_width=9, frame_height=16, background_color=FONDO)


def dibujar(cam, mobs):
    cam.reset()
    cam.capture_mobjects(mobs)
    return cam.pixel_array.copy()


def vacio():
    return dibujar(camara(Camera), [])


def igual_a_manim(mobs, que):
    a = dibujar(camara(Camera), mobs)
    b = dibujar(camara(CamaraEstudio), mobs)
    if not np.array_equal(a, b):
        n = int(np.any(a != b, axis=2).sum())
        raise AssertionError(f"{que}: CamaraEstudio difiere de Camera en {n} píxeles")
    return a


def no_dibuja(mob, que):
    cam = camara(CamaraEstudio)
    if cam.get_mobjects_to_display([mob]):
        raise AssertionError(f"{que}: CamaraEstudio debería descartarlo y no lo descarta")
    if not np.array_equal(dibujar(cam, [mob]), vacio()):
        raise AssertionError(f"{que}: deja algo dibujado")


# ---------------------------------------------------------------- FALLO 1 · objetos que cruzan la pantalla
def p1a_linea_que_cruza():
    m = Line([-10, 0, 0], [10, 0, 0], color=TIZA, stroke_width=8)
    if np.array_equal(igual_a_manim([m], "línea de -10 a 10"), vacio()):
        raise AssertionError("línea de -10 a 10: Camera tampoco dibuja nada (prueba mal planteada)")


def p1b_curva_extremos_fuera():
    m = VMobject(stroke_color=CALIENTE, stroke_width=8)
    m.set_points_smoothly([[-10, -10, 0], [0, 0, 0], [10, -10, 0]])
    if np.array_equal(igual_a_manim([m], "curva con los extremos fuera"), vacio()):
        raise AssertionError("curva con los extremos fuera: Camera tampoco dibuja nada (prueba mal planteada)")


def p1c_medio_dentro():
    m = Circle(radius=3.5, color=AMBAR, stroke_width=8).move_to([7, 0, 0])     # de x=3,5 a x=10,5; empieza y acaba en x=10,5
    m.set_fill(AMBAR, opacity=0.5)
    if np.array_equal(igual_a_manim([m], "círculo medio dentro"), vacio()):
        raise AssertionError("círculo medio dentro: Camera tampoco dibuja nada (prueba mal planteada)")


def p1c2_borde_por_el_trazo():
    m = Line([-3, 8.05, 0], [3, 8.05, 0], color=TIZA, stroke_width=20)          # fuera por 0,05; el trazo mide 0,2
    igual_a_manim([m], "línea justo encima del borde, visible por su grosor")


def p1d_entero_fuera():
    m = Square(side_length=2, color=TIZA, stroke_width=8).move_to([8, 0, 0])   # de x=7 a x=9: fuera (borde en 4,5)
    igual_a_manim([m], "cuadrado entero fuera")
    no_dibuja(m, "cuadrado entero fuera")


def p1e_aparcados():
    abajo = Square(side_length=1, color=TIZA).move_to([0, -40000, 0])
    arriba = Square(side_length=1, color=TIZA).move_to([0, 60, 0])
    no_dibuja(abajo, "objeto aparcado en y=-40000")
    no_dibuja(arriba, "objeto aparcado en y=60")


def p1f_transparente():
    m = Square(side_length=2, color=TIZA).set_stroke(opacity=0)
    igual_a_manim([m], "cuadrado transparente")
    no_dibuja(m, "cuadrado transparente")


# ---------------------------------------------------------------- FALLO 4 · caché de fondos
def imagen_blanca():
    img = ImageMobject(np.full((64, 64, 4), 255, dtype=np.uint8))
    img.height = 4
    return img


def p4a_cambio_de_pixeles():
    img = imagen_blanca()
    cam = camara(CamaraEstudio)
    dibujar(cam, [img])
    img.pixel_array[1:10, 1:10, :3] = 0
    segunda = dibujar(cam, [img])
    if not np.array_equal(segunda, dibujar(camara(Camera), [img])):
        raise AssertionError("imagen con 9x9 píxeles cambiados: la misma CamaraEstudio sigue mostrando la imagen vieja")


def p4b_cambio_de_opacidad():
    img = imagen_blanca()
    cam = camara(CamaraEstudio)
    dibujar(cam, [img])
    img.set_opacity(0.4)
    segunda = dibujar(cam, [img])
    if not np.array_equal(segunda, dibujar(camara(Camera), [img])):
        raise AssertionError("imagen con otra opacidad: la misma CamaraEstudio sigue mostrando la imagen vieja")


def p4c_cambio_de_posicion():
    img = imagen_blanca()
    cam = camara(CamaraEstudio)
    dibujar(cam, [img])
    img.shift([1, 2, 0])
    segunda = dibujar(cam, [img])
    if not np.array_equal(segunda, dibujar(camara(Camera), [img])):
        raise AssertionError("imagen movida: la misma CamaraEstudio la dibuja en el sitio viejo")


def p4d_repetir_igual():
    img = imagen_blanca()
    img.pixel_array[5:20, 5:20, :3] = 30
    cam = camara(CamaraEstudio)
    primera = dibujar(cam, [img])
    segunda = dibujar(cam, [img])
    if not (np.array_equal(primera, segunda) and np.array_equal(segunda, dibujar(camara(Camera), [img]))):
        raise AssertionError("imagen sin cambios dibujada dos veces: el resultado guardado no es idéntico al de Camera")


# ================================================================ DETECTOR DE COMPOSICIÓN (motor/choques.py)
from types import SimpleNamespace                     # noqa: E402

from manim import Create, FadeIn, Integer, Rectangle, Text, VGroup  # noqa: E402

import choques                                       # noqa: E402
from nucleo import FUENTE, EscenaEstudio, UpdateFromAlphaFunc, pildora  # noqa: E402
from personajes.demo import Demo                   # noqa: E402


def texto(s, x, y, tam=24):
    return Text(s, font=FUENTE, font_size=tam, color=TIZA).move_to([x, y, 0])


def rejilla(n, y0=5.0):
    """n textos separados entre sí, dentro de la zona segura."""
    return [texto(f"texto {i}", -2.6 + 2.6 * (i % 3), y0 - 1.2 * (i // 3)) for i in range(n)]


def escena_falsa(*mobs, t=0.0):
    return SimpleNamespace(mobjects=list(mobs), _hud=[], t=t, g=SimpleNamespace(palabras=[], beats=[]))


def hallazgos(*mobs):
    return choques.revisar(choques.recoger(escena_falsa(*mobs)))


def tipos(hs, tipo):
    return [h for h in hs if h["tipo"] == tipo]


# ---------------------------------------------------------------- FALLO 2a · textos a la vez (bloques de lectura)
def p2a_ocho_no_avisa():
    hs = hallazgos(*rejilla(8))
    if tipos(hs, "exceso"):
        raise AssertionError(f"8 bloques visibles: avisa de exceso ({tipos(hs, 'exceso')[0]['texto']})")


def p2a_nueve_avisa():
    mobs = rejilla(8) + [Integer(7, font_size=24).move_to([0, -2.5, 0])]       # el noveno es un número suelto
    if not tipos(hallazgos(*mobs), "exceso"):
        raise AssertionError("8 textos + 1 número suelto = 9 bloques: no avisa de exceso")


def p2a_letra_cuenta():
    mobs = rejilla(8) + [texto("z", 0, -2.5)]
    if not tipos(hallazgos(*mobs), "exceso"):
        raise AssertionError("8 textos + la letra «z» = 9 bloques: no avisa de exceso")


def p2a_grupo_lectura_cuenta_uno():
    grupo = VGroup(*[texto(f"g{i}", -2.6 + 1.3 * i, -2.5) for i in range(5)])
    grupo.lectura = "grupo de prueba"
    hs = hallazgos(*rejilla(7), grupo)
    if tipos(hs, "exceso"):
        raise AssertionError(f"7 textos + un grupo lectura= con 5 textos = 8 bloques: avisa ({tipos(hs, 'exceso')[0]['texto']})")


# ---------------------------------------------------------------- FALLO 2b · textos nuevos por beat
def registro_con(*fotos):
    """fotos: (beat, [mobjects]). Devuelve los hallazgos «nuevos» del registro."""
    r = choques.Registro()
    for i, (beat, mobs) in enumerate(fotos):
        r.foto(escena_falsa(*mobs, t=float(i)), beat, -4.8, 3.15)
    return [v for v in r.vistos.values() if v["tipo"] == "nuevos"]


def p2b_dos_nuevos_no_avisa():
    a, b, c, d = rejilla(4)
    n = registro_con(("b1", [a, b]), ("b2", [a, b, c, d]))
    if n:
        raise AssertionError(f"b2 trae 2 textos nuevos y avisa: {n[0]['texto']}")


def p2b_tres_nuevos_avisa():
    a, b, c, d, e = rejilla(5)
    n = registro_con(("b1", [a, b]), ("b2", [a, b, c]), ("b2", [a, b, c, d, e]))
    if not n or "b2" not in n[0]["beats"]:
        raise AssertionError("b2 trae 3 textos nuevos (en dos fotos) y no avisa con tipo «nuevos» en b2")


def p2b_contador_que_cambia():
    a, b, c = rejilla(3)
    num = Integer(3, font_size=24).move_to([0, -2.5, 0])
    fotos = [("b1", [a, num])]
    num2 = num                       # el mismo objeto, con otro valor
    num2.set_value(41)
    fotos.append(("b2", [a, num2, b, c]))
    n = registro_con(*fotos)
    if n:
        raise AssertionError(f"el contador cambió de valor y cuenta como nuevo: {n[0]['texto']}")


def p2b_relevo_cuenta():
    a, x = rejilla(2)
    r1, r2, r3 = (texto(s, 0, -2.2) for s in ("primera aclaración", "segunda aclaración", "tercera aclaración"))
    n = registro_con(("b1", [a, r1]), ("b2", [a, r2]), ("b2", [a, r3, x]))
    if not n:
        raise AssertionError("b2: dos relevos de rótulo + un texto = 3 nuevos, y no avisa")


# ---------------------------------------------------------------- FALLO 3A · «uno dentro de otro» solo por pertenencia
def p3a_independientes_se_pisan():
    a = dict(tipo="objeto", nombre="A", caja=[-2, 0, 0, 1], tam=None, hud=False, orden=1, texto="", id=1, anc=(), cont=())
    b = dict(tipo="objeto", nombre="B", caja=[-1.5, 0, 0.5, 1], tam=None, hud=False, orden=2, texto="", id=2, anc=(), cont=())
    if not tipos(choques.revisar([a, b]), "solape"):
        raise AssertionError("dos objetos importantes independientes que se pisan: no da solape")


def p3a_texto_en_su_pildora():
    hs = hallazgos(pildora("T constante", TIZA, 24).move_to([0, 3, 0]))
    if tipos(hs, "solape"):
        raise AssertionError(f"el texto dentro de su píldora da falsa alarma: {tipos(hs, 'solape')[0]['texto']}")


def p3a_personaje_en_contenedor():
    from manim import VGroup, Rectangle
    actor = Demo(pos=(0,0), escala=.5)
    fondo = Rectangle(width=3,height=3).move_to(actor.get_center())
    grupo = VGroup(fondo, actor); grupo.contenedor = True
    hs = hallazgos(grupo)
    assert not tipos(hs,'solape'), hs


# ---------------------------------------------------------------- FALLO 3B · velos semitransparentes
def velo(op):
    return Rectangle(width=9.4, height=16.4, stroke_width=0, fill_color=FONDO, fill_opacity=op)


def pisados():
    return texto("primer texto", 0, 1), texto("segundo texto", 0.4, 1.05)


def p3b_velo_60_se_ve():
    a, b = pisados()
    if not tipos(hallazgos(a, b, velo(0.6)), "solape"):
        raise AssertionError("dos textos que se pisan tras un velo al 60 % (se siguen viendo): no se detectan")


def p3b_velo_93_tapa():
    a, b = pisados()
    hs = tipos(hallazgos(a, b, velo(0.93)), "solape")
    if hs:
        raise AssertionError(f"dos textos tras el velo de enfocar() (93 %) cuentan como visibles: {hs[0]['texto']}")


def p3b_z_index_sobre_velo():
    a, b = pisados()
    a.set_z_index(2)
    b.set_z_index(2)
    if not tipos(hallazgos(a, b, velo(0.93)), "solape"):
        raise AssertionError("dos textos con z_index mayor que el velo (se dibujan encima): no se detectan")


# ---------------------------------------------------------------- Protecciones de grupos vivos (EscenaEstudio)
class _EscenaSinGuion(EscenaEstudio):
    def setup(self):
        self._vigila = True


def grupo_vivo():
    hijo = Square(side_length=1, color=TIZA).set_stroke(opacity=0.8)
    grupo = VGroup(Circle(radius=1, color=AMBAR), hijo)
    grupo.pasos = 0

    def latido(m, dt):
        m.pasos += 1
    grupo.add_updater(latido)
    esc = _EscenaSinGuion()
    esc.setup()
    esc.add(grupo)
    return esc, grupo, hijo


def pg_fadein_se_convierte():
    esc, grupo, hijo = grupo_vivo()
    anim = esc._vigilar(FadeIn(hijo))
    if isinstance(anim, FadeIn) or not isinstance(anim, UpdateFromAlphaFunc) or anim.is_introducer():
        raise AssertionError(f"FadeIn simple sobre un objeto interno no se convierte en aparecer() (queda {type(anim).__name__})")
    anim.begin()
    anim.interpolate(1.0)
    anim.finish()
    if abs(hijo.get_stroke_opacity() - 0.8) > 1e-6:
        raise AssertionError(f"tras aparecer() la opacidad del objeto es {hijo.get_stroke_opacity():.2f}, no 0,80")
    antes = grupo.pasos
    esc.update_mobjects(0.1)
    if esc.mobjects != [grupo] or grupo.pasos != antes + 1 or hijo not in grupo.submobjects:
        raise AssertionError("tras el FadeIn convertido el grupo se partió o dejó de actualizarse")


def pg_create_se_detiene():
    esc, _, hijo = grupo_vivo()
    try:
        esc._vigilar(Create(hijo))
    except ValueError:
        return
    raise AssertionError("Create sobre un objeto interno de un grupo vivo no se detiene con ValueError")


def pg_add_se_detiene():
    esc, _, hijo = grupo_vivo()
    try:
        esc.add(hijo)
    except ValueError:
        return
    raise AssertionError("self.add() de un objeto interno de un grupo vivo no se detiene con ValueError")


PRUEBAS = [
    ("1a · línea que cruza la pantalla", p1a_linea_que_cruza),
    ("1b · curva con extremos fuera y centro dentro", p1b_curva_extremos_fuera),
    ("1c · objeto medio dentro", p1c_medio_dentro),
    ("1c · borde visible solo por el grosor del trazo", p1c2_borde_por_el_trazo),
    ("1d · objeto entero fuera: no se dibuja", p1d_entero_fuera),
    ("1e · objetos aparcados (y=-40000, y=60): no se dibujan", p1e_aparcados),
    ("1f · objeto transparente: no se dibuja", p1f_transparente),
    ("4a · caché: cambian píxeles de la imagen", p4a_cambio_de_pixeles),
    ("4b · caché: cambia la opacidad de la imagen", p4b_cambio_de_opacidad),
    ("4c · caché: la imagen se mueve", p4c_cambio_de_posicion),
    ("4d · caché: la misma imagen dos veces", p4d_repetir_igual),
    ("2a · 8 bloques a la vez: no avisa", p2a_ocho_no_avisa),
    ("2a · 9 bloques (el noveno, un número): avisa", p2a_nueve_avisa),
    ("2a · 9 bloques (el noveno, una letra): avisa", p2a_letra_cuenta),
    ("2a · grupo lectura= con 5 textos cuenta 1", p2a_grupo_lectura_cuenta_uno),
    ("2b · 2 textos nuevos en un beat: no avisa", p2b_dos_nuevos_no_avisa),
    ("2b · 3 textos nuevos en un beat: avisa «nuevos»", p2b_tres_nuevos_avisa),
    ("2b · un contador que cambia no es nuevo", p2b_contador_que_cambia),
    ("2b · un relevo de rótulo cuenta como nuevo", p2b_relevo_cuenta),
    ("3A · objetos independientes que se pisan: solape", p3a_independientes_se_pisan),
    ("3A · el texto dentro de su píldora: sin alarma", p3a_texto_en_su_pildora),
    ("3A · personaje dentro de contenedor: sin alarma", p3a_personaje_en_contenedor),
    ("3B · textos que se pisan tras un velo al 60 %: se detectan", p3b_velo_60_se_ve),
    ("3B · textos tras el velo de enfocar() (93 %): no cuentan", p3b_velo_93_tapa),
    ("3B · textos con z_index sobre el velo: se detectan", p3b_z_index_sobre_velo),
    ("grupos · FadeIn simple interno se convierte y el grupo sigue vivo", pg_fadein_se_convierte),
    ("grupos · Create interno se detiene con ValueError", pg_create_se_detiene),
    ("grupos · self.add() interno se detiene con ValueError", pg_add_se_detiene),
]


from pruebas_mejoras import PRUEBAS as PRUEBAS_MEJORAS
PRUEBAS += PRUEBAS_MEJORAS
from pruebas_validar import PRUEBAS as PRUEBAS_VALIDAR   # validador de guiones (2026-11-13)
PRUEBAS += PRUEBAS_VALIDAR
from pruebas_encuadre import PRUEBAS as PRUEBAS_ENCUADRE   # encuadre y audio completo
PRUEBAS += PRUEBAS_ENCUADRE
from pruebas_flujo import PRUEBAS as PRUEBAS_FLUJO
PRUEBAS += PRUEBAS_FLUJO
from pruebas_actuacion import PRUEBAS as PRUEBAS_ACTUACION   # recetas de actuación con objetos
PRUEBAS += PRUEBAS_ACTUACION
from pruebas_voz import PRUEBAS as PRUEBAS_VOZ   # filtro de pronunciación (2026-11-13)
PRUEBAS += PRUEBAS_VOZ
from pruebas_corte import PRUEBAS as PRUEBAS_CORTE   # corte, cola de voz, esquema y sugerencia (2026-11-14)
PRUEBAS += PRUEBAS_CORTE
from pruebas_configuracion import PRUEBAS as PRUEBAS_CONFIGURACION
PRUEBAS += PRUEBAS_CONFIGURACION
from pruebas_registro import PRUEBAS as PRUEBAS_REGISTRO
PRUEBAS += PRUEBAS_REGISTRO
from pruebas_detector import PRUEBAS as PRUEBAS_DETECTOR
PRUEBAS += PRUEBAS_DETECTOR
from pruebas_compatibilidad import PRUEBAS as PRUEBAS_COMPATIBILIDAD
PRUEBAS += PRUEBAS_COMPATIBILIDAD


def main():
    fallidas = []
    for nombre, f in PRUEBAS:
        try:
            f()
            print(f"  OK     {nombre}")
        except AssertionError as e:
            print(f"  FALLA  {nombre}: {e}")
            fallidas.append(nombre)
        except Exception:
            print(f"  ERROR  {nombre}:")
            traceback.print_exc()
            fallidas.append(nombre)
    if fallidas:
        print(f"\nFALLAN {len(fallidas)} de {len(PRUEBAS)}:")
        for n in fallidas:
            print(f"  - {n}")
        return 1
    print(f"\nTODO BIEN ({len(PRUEBAS)} pruebas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
