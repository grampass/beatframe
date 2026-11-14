"""Contrato técnico: los casos editoriales pertenecen a las extensiones."""
import json
import tempfile
from pathlib import Path

from validar import validar


def _guion():
    return dict(id="EJEMPLO", titulo="Movimiento", curso="general", especialista="demo", concepto="Un movimiento",
                beats=[dict(id="b1", personaje="demo", voz="voz-prueba", texto="La pieza se mueve.",
                            escenario="vacio", visual="Un disco avanza.")])


def _validar(g, tiempos=None, audio=b"audio"):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "guion.json").write_text(json.dumps(g), encoding="utf-8")
        if tiempos is not None:
            (p / "audio").mkdir()
            (p / "audio/tiempos.json").write_text(json.dumps(tiempos), encoding="utf-8")
            if audio is not None:
                (p / "audio/b1.mp3").write_bytes(audio)
        return validar(p, con_audio=tiempos is not None)


def v_contrato_minimo_sin_politica_editorial():
    assert _validar(_guion()) == ([], [])


def v_json_invalido_se_informa():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); (p / "guion.json").write_text("{")
        e, _ = validar(p)
        assert e and "No se puede leer" in e[0], e


def v_campos_obligatorios():
    for campo in ("id", "titulo", "curso", "especialista", "concepto"):
        g = _guion(); del g[campo]
        assert _validar(g)[0], campo


def v_voz_explicita_sin_asignaciones():
    g = _guion(); del g["beats"][0]["voz"]
    assert any("voz" in e for e in _validar(g)[0])


def v_identificadores_repetidos_y_rutas():
    g = _guion(); g["beats"] *= 2
    assert any("repetido" in e for e in _validar(g)[0])
    g = _guion(); g["beats"][0]["id"] = "../fuera"
    assert any("id inválido" in e for e in _validar(g)[0])


def v_parametros_no_finitos_y_tipos():
    for clave, valor in (("cola", -1), ("cola", float("nan")), ("rate", 8), ("pitch", "3Hz"),
                         ("acciones", [None]), ("claves", [])):
        g = _guion(); g["beats"][0][clave] = valor
        assert _validar(g)[0], (clave, valor)


def v_palabras_vacias_y_desordenadas():
    for pal in ([], [dict(w="", t=0, d=1)], [dict(w="dos", t=1,d=.1),dict(w="uno",t=0,d=.1)]):
        assert _validar(_guion(), {"b1":pal})[0], pal


def v_audio_ausente_y_vacio():
    for audio in (None, b""):
        assert any("audio ausente" in e for e in _validar(_guion(), {"b1":[dict(w="pieza",t=0,d=1)]}, audio)[0])


def v_audio_y_tiempos_tecnicos_validos():
    assert _validar(_guion(), {"b1":[dict(w="pieza",t=0,d=1)]}) == ([], [])


def v_metadatos_no_crean_politica_automatica():
    g = _guion(); g.update(estado="aprobado", ficha="referencia.md", verificacion="revision.md")
    assert _validar(g) == ([], [])


PRUEBAS = [(n,f) for n,f in globals().items() if n.startswith("v_") and callable(f)]
