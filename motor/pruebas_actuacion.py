"""Pruebas de las recetas de actuación con objetos. Se ejecutan desde pruebas_motor.py.

Previenen: la mano que no llega al punto pedido si personaje no está en su posición oficial; la taza que se separa de la
mano al empujarla; la nota de inserto que queda de la cara equivocada tras dos giros; el texto que se sale del papel;
la taza vacía que se «llena» si alguien le cambia la temperatura.
"""
import numpy as np

from personajes.demo import Demo
from pruebas_soporte import registro_demo
from piezas.objetos import ManoInserto, NotaGrande, NotaMesa, TazaVacia, empujar


def _correr(*anims):
    for a in anims:
        a.begin(); a.interpolate(1.0); a.finish()


def a_alcanzar_lleva_la_mano_al_punto():
    for pos, e in (((0.0, -3.13), 1.0), ((1.2, -2.5), 0.8)):
        actor = Demo(pos=pos, escala=e)
        for x, y in ((2.0, -4.6), (-0.5, -3.7), (3.1, -3.5)):
            actor.poner(**actor.alcanzar(x, y))
            assert np.allclose(actor.punto(*actor.mano)[:2], (x, y), atol=1e-6), f"mano en {actor.punto(*actor.mano)[:2]}, pedida {(x, y)}"


def a_empujar_mueve_taza_y_mano_juntas():
    actor, taza = Demo(), TazaVacia((2.0, -5.75), 0.8)
    antes = taza.get_center().copy()
    actor.poner(**actor.alcanzar(*taza.borde()))
    _correr(*empujar(actor, taza, (1.45, -5.85)))
    assert np.allclose(taza.base, (1.45, -5.85)), "La base registrada no es el destino"
    assert np.allclose(taza.get_center() - antes, (-0.55, -0.10, 0), atol=1e-6), "La taza no se desplazó lo pedido"
    assert np.allclose(actor.punto(*actor.mano)[:2], taza.borde(), atol=1e-6), "La mano no quedó en el borde de la taza"


def a_demo_alcanza_con_espejo_giro_y_aplastado():
    for espejo in (False, True):
        actor = Demo(pos=(.8,-1.2), escala=.7)
        actor.espejo = espejo
        actor.poner(incl=32, aplastar=.65)
        for objetivo in ((-1.0,.5), (2.2,-1.8)):
            actor.poner(**actor.alcanzar(*objetivo))
            assert np.allclose(actor.submobjects[-1].get_center()[:2], objetivo, atol=1e-6)


def a_taza_vacia_no_se_llena():
    t = TazaVacia((0, 0), 0.8)
    color = t.cuerpo.get_fill_color().to_hex()
    t.set_temp(1.0)
    assert t.cuerpo.get_fill_color().to_hex() == color and t.vapor.get_stroke_opacity() == 0, "La taza vacía cambió"


def a_nota_grande_dos_giros_vuelve_boca_abajo():
    n = NotaGrande("Una frase bastante larga para el papel")
    assert n.letra.width <= 3.4 * 0.8 + 1e-6, "El texto se sale del papel"
    ancho = n.width
    _correr(n.girar())
    assert n.boca_arriba and n.cara.get_fill_opacity() > 0.9 and n.dorso.get_fill_opacity() < 0.1, "No quedó boca arriba"
    assert abs(n.width - ancho) < 1e-6, "Tras el giro cambió de ancho"
    _correr(n.girar())
    assert not n.boca_arriba and n.dorso.get_fill_opacity() > 0.9 and n.cara.get_fill_opacity() < 0.1, "No volvió boca abajo"


def a_piezas_sin_texto_en_mesa():
    assert not any(type(m).__name__ in ("Text", "MarkupText") for m in NotaMesa(0, 0, 8).get_family()), "La nota de mesa tiene texto"
    with registro_demo():
        assert len(ManoInserto((0, 0)).submobjects) == 1




# ---------- Generador de borradores v2 (objetos y acciones) ----------
def _generar(g):
    import ast, json, tempfile
    from pathlib import Path
    from generar_escena import crear
    with tempfile.TemporaryDirectory(prefix="motor-gen-") as d:
        p = Path(d)
        (p / "guion.json").write_text(json.dumps(g, ensure_ascii=False), encoding="utf-8")
        with registro_demo():
            f = crear(p)
        s = f.read_text(encoding="utf-8")
        ast.parse(s)
        return s


def _guion_gen(**extra_b1):
    b1 = dict(id="b1", personaje="actor", texto="Ya moví la pieza.", visual="La empuja.", acciones=[
        dict(palabra="Ya", hace="empujar", objeto="taza2", hasta=[-0.6, -3.9]),
        dict(palabra="pieza", hace="leer_nota", texto="Listo para probar")], **extra_b1)
    b2 = dict(id="b2", personaje="actor", texto="La pieza queda lista.", visual="Toca su taza y la mira.")
    return dict(receta="demostracion", objetos={"taza2": dict(tipo="TazaVacia", pos=[-0.15, -3.86], escala=0.6,
                                                                importante=True, tocado=True)}, beats=[b1, b2])


def a_generador_convierte_acciones():
    s = _generar(_guion_gen())
    assert "taza2 = TazaVacia((-0.15, -3.86), 0.6)" in s and "taza2.importante = True" in s
    assert "self.montar('demostracion', tocados=(taza2,))" in s, s
    assert "*empujar(personaje, taza2, (-0.6, -3.9))" in s and "NotaGrande('Listo para probar')" in s
    assert "self.desenfocar_anim(ambiente='laboratorio')" in s, "El inserto de b1 no se cierra al pasar a b2"
    assert "# Sugerencia: personaje.anim(**personaje.alcanzar" in s, "b2 sin acciones no recibe sugerencias"
    assert "pendiente_animar = True" in s
    assert s.index("self.montar(") < s.index("self.hasta(g['b1']['ini'])"), "El escenario se monta después de esperar"


def a_generador_rechaza_acciones_invalidas():
    for cambio, motivo in ((dict(hace="volar"), "acción desconocida"), (dict(palabra="nunca"), "palabra ausente"),
                           (dict(objeto="taza9"), "objeto no declarado")):
        g = _guion_gen()
        g["beats"][0]["acciones"][0].update(cambio)
        try:
            _generar(g)
        except ValueError:
            continue
        raise AssertionError(f"Aceptó {motivo}")


PRUEBAS = [(n, f) for n, f in globals().items() if n.startswith("a_") and callable(f)]
