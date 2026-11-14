"""Pruebas de las piezas nacidas de los fallos de la tanda del 2026-11-14: corte entre planos, cola de la voz,
esquema por partes y sugerencia en el aviso de retraso. Sin render: segundos."""
import contextlib
import io
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from manim import Dot, Square

from nucleo import EscenaEstudio, Esquema, instante_corte, sugerir_palabra


def c_corte_espera_a_mitad_de_pausa():
    assert abs(instante_corte([0.15, 3.0, 5.3], 5.08) - 5.2) < 1e-9


def c_corte_no_espera_al_inicio_ni_al_final():
    assert instante_corte([0.15, 3.0], 0.0) is None
    assert instante_corte([0.15, 3.0], 4.0) is None          # no queda beat: no rompe (antes, min() vacío)


def c_corte_tolera_reloj_adelantado():
    # a 15 fps el reloj pasa unas centésimas del inicio del beat: no se espera ni se rompe
    assert instante_corte([0.15, 3.0, 5.3], 5.33) is None
    assert instante_corte([0.15, 3.0, 5.3], 5.25) is None


def c_cubrir_voz_alarga_hasta_la_ultima_voz():
    esperas = []
    falsa = SimpleNamespace(carpeta=".", _tramo=None, renderer=SimpleNamespace(time=10.0),
                            fin_voz=lambda: 10.24, wait=esperas.append)
    assert abs(EscenaEstudio.cubrir_voz(falsa) - 0.24) < 1e-9
    assert len(esperas) == 1 and abs(esperas[0] - 0.24) < 1e-9


def c_cubrir_voz_no_toca_lo_que_ya_cubre():
    esperas = []
    falsa = SimpleNamespace(carpeta=".", _tramo=None, renderer=SimpleNamespace(time=10.3),
                            fin_voz=lambda: 10.24, wait=esperas.append)
    assert EscenaEstudio.cubrir_voz(falsa) == 0.0 and not esperas
    falsa.renderer.time, falsa._tramo = 10.0, (2.0, 4.0)      # render por tramos: no se alarga
    assert EscenaEstudio.cubrir_voz(falsa) == 0.0 and not esperas


def c_esquema_coloca_tambien_las_partes_futuras():
    e = Esquema()
    e.parte("base", Square(side_length=1).move_to([1, 0, 0]), visible=True)
    e.parte("luego", Dot([1, 0, 0]))
    e.colocar(0.5, (2, 3))
    assert np.allclose(e.base.get_center(), [2.5, 3, 0]) and np.allclose(e.luego.get_center(), [2.5, 3, 0])
    assert e.luego not in e.submobjects and abs(e.base.width - 0.5) < 1e-6


def c_esquema_rechaza_nombres_que_chocan():
    e = Esquema()
    e.parte("ondas", Dot())
    for nombre in ("ondas", "color"):
        try:
            e.parte(nombre, Dot())
        except ValueError:
            continue
        raise AssertionError(f"aceptó la parte «{nombre}»")


def c_sugerencia_de_palabra_que_cabe():
    pal = [dict(w="El", t=1.0, d=0.1), dict(w="aire", t=1.4, d=0.3), dict(w="sale,", t=2.0, d=0.3)]
    assert sugerir_palabra(pal, 0.9, 2.2, antes=0.15, min_dur=0.6) == "aire"
    assert sugerir_palabra(pal, 1.9, 2.2, antes=0.15, min_dur=0.6) is None



def c_montar_corta_aplica_ajustes_y_objetos():
    llamadas = []
    pers = SimpleNamespace(poner=lambda **k: llamadas.append(("poner", k)))
    montaje = SimpleNamespace(personaje=pers)
    falsa = SimpleNamespace(corte=lambda: llamadas.append(("corte",)))
    nota, caja = object(), object()
    with patch("recetas.aplicar_receta", lambda esc, r, **aj: llamadas.append(("receta", r, aj)) or montaje), \
         patch("recetas.objetos_en_mesa", lambda esc, m, *objs, tocados=(): llamadas.append(("mesa", objs, tocados))):
        assert EscenaEstudio.montar(falsa, "plano-a", caja, tocados=(nota,), poner=dict(gesto=1), luz="baja") is montaje
    assert llamadas == [("corte",), ("receta", "plano-a", {"luz": "baja"}), ("mesa", (caja, nota), (nota,)),
                        ("poner", {"gesto": 1})], llamadas


def c_ajustes_de_guion_y_de_llamada():
    from recetas import opciones_receta
    esc = SimpleNamespace(g=SimpleNamespace(ajustes_receta={"plano-a": {"color": "gris", "luz": "baja"}}))
    assert opciones_receta(esc, "plano-a", {"luz": "alta"}) == {"color": "gris", "luz": "alta"}
    assert opciones_receta(esc, "otra") == {} and opciones_receta(SimpleNamespace(), "plano-a") == {}


def c_contrato_ajustes_receta():
    from contrato import estructura
    assert any("ajustes_receta" in e for e in estructura(dict(ajustes_receta={"r": "fria"}, beats=[]), completo=False))
    assert not any("ajustes_receta" in e for e in estructura(dict(ajustes_receta={"r": {"luz": "tenue"}}, beats=[]), completo=False))


def c_frase_aprobada_es_la_oracion():
    from pronunciacion import frase_de
    assert frase_de("Ya lo guardé. Y sigo pensando.", 2) == "Ya lo guardé"
    assert frase_de("Sí, te avisé; no lo olvidé.", 2) == "Sí, te avisé"


def _carpeta_voz(d, texto="Me mudé. Y sigo."):
    p = Path(d)
    (p / "audio").mkdir()
    (p / "guion.json").write_text(json.dumps(dict(id="X", beats=[dict(id="b1", personaje="voz1", texto=texto)])), encoding="utf-8")
    (p / "audio" / "b1.mp3").write_bytes(b"audio de prueba")
    from artefactos import sha256
    (p / "audio" / "pronunciacion.json").write_text(json.dumps(
        {"b1": dict(sha256=sha256(p / "audio" / "b1.mp3"), oido=["Mi", "muro.", "Y", "sigo."])}), encoding="utf-8")
    return p


def c_aprobar_silencia_ese_audio_y_guarda_la_frase():
    import pronunciacion as P
    with tempfile.TemporaryDirectory() as d:
        p = _carpeta_voz(d)
        lex = p / "lexico.json"
        lex.write_text(json.dumps(dict(riesgo={}, aprobadas=[])), encoding="utf-8")
        with patch.object(P, "LEXICO", lex), patch.object(P, "escuchar", side_effect=AssertionError("no debe escuchar")):
            b = json.loads((p / "guion.json").read_text(encoding="utf-8"))["beats"][0]
            cache = json.loads((p / "audio" / "pronunciacion.json").read_text(encoding="utf-8"))
            assert P.revisar_beat(b, p / "audio" / "b1.mp3", {}, cache)[0], "debía marcar «mudé»"
            assert P.aprobar(p, ["b1"]) == ["Me mudé"]
            cache = json.loads((p / "audio" / "pronunciacion.json").read_text(encoding="utf-8"))
            assert P.revisar_beat(b, p / "audio" / "b1.mp3", {}, cache)[0] == []
            assert json.loads(lex.read_text(encoding="utf-8"))["aprobadas"] == ["Me mudé"]
            (p / "audio" / "b1.mp3").write_bytes(b"otra voz")            # voz nueva: la aprobación no vale
            with patch.object(P, "escuchar", return_value=["Mi", "muro.", "Y", "sigo."]):
                assert P.revisar_beat(b, p / "audio" / "b1.mp3", {}, cache)[0]
            P.marcar_riesgo(p, "b1", "Sigo", solo_inicio=True)
            assert json.loads(lex.read_text(encoding="utf-8"))["riesgo"]["sigo"]["voz"] == "voz1"


def c_producir_avisa_en_vista_previa_y_bloquea_el_final():
    import producir
    from flujo import Informe
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "audio").mkdir()
        (p / "audio" / "pronunciacion-marcas.json").write_text(json.dumps(
            {"b1": [dict(palabra="mudé", oido="muro", motivo="reconocedor")]}), encoding="utf-8")
        with patch.object(producir, "correr", return_value=(0, "ok")), contextlib.redirect_stdout(io.StringIO()):
            previa = Informe(p, "vista previa", "x")
            assert producir.revisar_pronunciacion(p, p, previa, final=False) is True
            assert any(a["codigo"] == "PRONUNCIACION" and "--aprobar b1" in a["mensaje"] for a in previa.avisos)
            assert not producir.revisar_pronunciacion(p, p, Informe(p, "final", "y"), final=True)
            (p / "audio" / "pronunciacion-marcas.json").write_text("{}", encoding="utf-8")
            assert producir.revisar_pronunciacion(p, p, Informe(p, "final", "z"), final=True)


def c_vista_previa_comprueba_tambien_a_30_fps():
    from pruebas_flujo import Simulador, audio_fixture, fixture, simular
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); g = fixture(p); audio_fixture(p, g)
        s = Simulador(p)
        vistos = []
        orig = s.correr
        def correr(cmd, cwd=None, env=None):
            if env and env.get("SOLO_CHOQUES") == "1":
                vistos.append(env.get("CALIDAD"))
            return orig(cmd, cwd, env)
        s.correr = correr
        assert simular(p, s) == 0
        assert sorted(vistos) == ["alta", "baja"], vistos       # en paralelo: el orden no importa
        vistos.clear()
        assert simular(p, s) == 0 and vistos == [], "con la escena igual, la comprobación a 30 fps se reutiliza"


def c_srt_frases_y_marcas():
    from subtitulos import cues, srt
    pal = [dict(w=w, t=0.2 + 0.3 * i, d=0.25) for i, w in enumerate("hola mundo esto sigue".split())]
    b = dict(texto="Hola, mundo. Esto sigue.", palabras=pal)
    c = cues([b])
    assert [x[2] for x in c] == ["Hola, mundo.", "Esto sigue."], c
    assert c[0][1] <= c[1][0], "dos subtítulos a la vez"
    salto = chr(10)
    texto = srt(c)
    assert texto.startswith("1" + salto + "00:00:00,200 --> 00:00:00,") and salto + "2" + salto in texto
    largo = dict(texto=" ".join(["palabra"] * 12), palabras=[dict(w="palabra", t=i * 0.3, d=0.25) for i in range(12)])
    assert all(len(x[2]) <= 42 for x in cues([largo]))


def c_miniatura_titulo_cabe():
    from PIL import Image, ImageDraw
    from miniatura import fuente, titulo_en
    img = Image.new("RGB", (600, 400))
    tam = titulo_en(img, "UNA PALABRAMUYLARGUISIMAQUENOCABE", (10, 10, 400, 390), 120)
    ancho = max(ImageDraw.Draw(img).textlength(l, font=fuente(tam)) for l in ["UNA", "PALABRAMUYLARGUISIMAQUENOCABE"])
    assert ancho <= 390, f"el título se sale ({ancho:.0f} px)"


def c_recopilacion_capitulos():
    from recopilar import capitulos, marca
    assert marca(0) == "0:00" and marca(64.9) == "1:04" and marca(3725) == "1:02:05"
    assert capitulos(["A", "B"], [0.0, 64.2]).splitlines() == ["0:00 A", "1:04 B"]


def c_final_reutiliza_la_comprobacion_30fps():
    from pruebas_flujo import Simulador, audio_fixture, fixture, simular
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); g = fixture(p); audio_fixture(p, g)
        s = Simulador(p)
        vistos = []
        orig = s.correr
        def correr(cmd, cwd=None, env=None):
            if env and env.get("SOLO_CHOQUES") == "1":
                vistos.append(env.get("CALIDAD"))
            return orig(cmd, cwd, env)
        s.correr = correr
        assert simular(p, s) == 0 and sorted(vistos) == ["alta", "baja"], vistos
        vistos.clear()
        with patch("producir.preparar_revision", return_value="vigente"):
            simular(p, s, final=True)
        assert vistos == [], f"el final repitió la comprobación sin dibujar: {vistos}"

PRUEBAS = [
    ("corte · espera a mitad de la pausa antes del beat siguiente", c_corte_espera_a_mitad_de_pausa),
    ("corte · sin espera al inicio ni tras el último beat", c_corte_no_espera_al_inicio_ni_al_final),
    ("corte · tolera el reloj adelantado a 15 fps", c_corte_tolera_reloj_adelantado),
    ("cola · la imagen se alarga hasta la última voz", c_cubrir_voz_alarga_hasta_la_ultima_voz),
    ("cola · no alarga si ya cubre ni en tramos", c_cubrir_voz_no_toca_lo_que_ya_cubre),
    ("esquema · las partes que entran después caen en su sitio", c_esquema_coloca_tambien_las_partes_futuras),
    ("esquema · rechaza nombres repetidos o de VGroup", c_esquema_rechaza_nombres_que_chocan),
    ("retraso · sugiere la última palabra donde cabe", c_sugerencia_de_palabra_que_cabe),
    ("diálogo · montar(): corte, ajustes, objetos fijos y pose", c_montar_corta_aplica_ajustes_y_objetos),
    ("receta · ajustes del guion bajo los de la llamada", c_ajustes_de_guion_y_de_llamada),
    ("contrato · ajustes_receta es {receta: {ajuste: valor}}", c_contrato_ajustes_receta),
    ("voz · la frase aprobada es la oración de la palabra", c_frase_aprobada_es_la_oracion),
    ("voz · aprobar silencia ese audio, guarda la frase y caduca con voz nueva", c_aprobar_silencia_ese_audio_y_guarda_la_frase),
    ("voz · producir avisa en la vista previa y bloquea el final", c_producir_avisa_en_vista_previa_y_bloquea_el_final),
    ("flujo · la vista previa también comprueba a 30 fps (con caché)", c_vista_previa_comprueba_tambien_a_30_fps),
    ("srt · frases con el texto del guion, sin solaparse", c_srt_frases_y_marcas),
    ("miniatura · el título cabe aunque una palabra sea larga", c_miniatura_titulo_cabe),
    ("recopilación · marcas de capítulo para la descripción", c_recopilacion_capitulos),
    ("flujo · el final reutiliza la comprobación a 30 fps de la vista previa", c_final_reutiliza_la_comprobacion_30fps),
]
