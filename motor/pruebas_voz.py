"""Pruebas del filtro de pronunciación sin red ni reconocedor: comparan textos ya «oídos».
Se ejecutan desde pruebas_motor.py; los casos específicos se separarán de las pruebas genéricas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pronunciacion import (comparar, mas_lento, normalizar, palabras_texto, riesgos,  # noqa: E402
                           variantes_texto)


def a_normalizar_ignora_seseo_y_tildes():
    for a, b in (("taza", "tasa"), ("tú", "tu"), ("vuelvas", "buelbas"), ("hace", "ace"), ("llama", "yama")):
        assert normalizar(a) == normalizar(b), (a, b)
    assert normalizar("preparé") != normalizar("preparo") and normalizar("moví") != normalizar("móvil")


def a_comparar_marca_lo_que_suena_distinto():
    m = comparar("Preparé. Moví la pieza.", ["Preparo.", "móvil", "la", "pieza."])
    assert [x["palabra"] for x in m] == ["Preparé", "Moví"], m
    assert m[0]["oido"].startswith("Preparo")         # un tramo sustituido muestra todo lo oído en él


def a_comparar_acepta_lo_aprobado():
    # lo que el reconocedor oyó en las voces aprobadas
    assert not comparar("Ya preparé la pieza. Sigue en su sitio.", ["Ya", "prepare", "la", "pieza", "Sigue", "en", "su", "sitio"])
    assert not comparar("La pieza quedó, y la revisaste.", ["la", "piesa", "quedó", "y", "la", "revisaste"])


def a_lexico_respeta_inicio_y_aprobadas():
    lex=dict(riesgo={'probé':dict(voz='demo',solo_inicio=True),'quedó':dict(voz='demo')},
             aprobadas=['La pieza quedó lista.'])
    assert [m['palabra'] for m in riesgos('Probé la pieza.','demo',lex)]==['Probé']
    assert not riesgos('Yo probé la pieza.','demo',lex)
    assert [m['palabra'] for m in riesgos('La pieza quedó atrás.','demo',lex)]==['quedó']
    assert not riesgos('La pieza quedó lista.','demo',lex)
    assert not riesgos('Probé la pieza.','otra',lex)


def a_variantes_solo_cambian_puntuacion():
    t = "La pieza quedó y la revisaste."
    i = [w for w, *_ in palabras_texto(t)].index("quedó")
    v = dict(variantes_texto(t, i))
    assert v == {"coma detrás": "La pieza quedó, y la revisaste.", "coma delante": "La pieza, quedó y la revisaste."}, v
    assert not dict(variantes_texto("Preparé.", 0))                  # al abrir y cerrar frase no hay coma posible
    assert mas_lento("-8%") == "-14%" and mas_lento("+0%") == "-6%"


PRUEBAS = [(n, f) for n, f in globals().items() if n.startswith("a_") and callable(f)]
