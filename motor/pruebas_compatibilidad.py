"""Compatibilidad de extensiones ficticias, sin depender de diseños privados."""
import json
import tempfile
from pathlib import Path

from pruebas_configuracion import proceso


def a_alias_conserva_identidad_y_nombre_en_ambos_ordenes():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "motor.json").write_text('{"configuracion":"."}', encoding="utf-8")
        (p / "config.json").write_text(json.dumps(dict(modulos_compatibles={
            "personajes.ejemplo": "componentes.actor", "piezas.ejemplo": "componentes.objeto"})), encoding="utf-8")
        (p / "componentes").mkdir()
        (p / "componentes/__init__.py").write_text("", encoding="utf-8")
        (p / "componentes/actor.py").write_text("class Actor: pass\n", encoding="utf-8")
        (p / "componentes/objeto.py").write_text("from personajes.ejemplo import Actor\n", encoding="utf-8")
        for orden in (("personajes.ejemplo", "componentes.actor"), ("componentes.actor", "personajes.ejemplo")):
            codigo = '''import sys, importlib
sys.path.insert(0, sys.argv[1])
a=importlib.import_module(sys.argv[2]); b=importlib.import_module(sys.argv[3])
assert a is b and a.Actor is b.Actor
assert a.__name__ == a.__spec__.name == 'componentes.actor'
assert importlib.reload(a) is a
import piezas.ejemplo as pieza
assert pieza.Actor is a.Actor
import personajes.ejemplo as antiguo
assert antiguo is a
print('OK')
'''
            assert proceso(codigo, p / "motor.json", p, *orden) == "OK"


def a_sin_config_no_se_instala_buscador_ni_alias():
    codigo = '''import importlib.util, sys
import personajes, piezas, compatibilidad
assert compatibilidad._BUSCADOR is None
assert importlib.util.find_spec('personajes.ejemplo') is None
assert not any(n.startswith('componentes') for n in sys.modules)
print('OK')
'''
    assert proceso(codigo) == "OK"


def a_alias_invalidos_fallan_sin_instalacion_parcial():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "motor.json").write_text('{"configuracion":"."}', encoding="utf-8")
        for alias in (["incorrecto"], {"personajes.a": "personajes.b", "personajes.b": "personajes.a"},
                      {"personajes.a": 42}, {"personajes.a": "sistema"}):
            (p / "config.json").write_text(json.dumps(dict(modulos_compatibles=alias)), encoding="utf-8")
            codigo = '''import compatibilidad
try: compatibilidad.instalar_compatibilidad()
except ValueError: pass
else: raise AssertionError('Aceptó alias inválidos')
assert compatibilidad._BUSCADOR is None
print('OK')
'''
            assert proceso(codigo, p / "motor.json") == "OK"


def a_regresion_sin_config_no_inventa_escenas():
    assert proceso("from regresion import ESCENAS; assert ESCENAS == []; print('OK')") == "OK"


def a_regresion_catalogo_configurado_y_rutas_invalidas():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "motor.json").write_text('{"configuracion":"."}', encoding="utf-8")
        (p / "config.json").write_text(json.dumps(dict(regresion=dict(escenas=["ejemplo", "_pruebas/actor"]))), encoding="utf-8")
        assert proceso("from regresion import ESCENAS; assert ESCENAS == ['ejemplo','_pruebas/actor']; print('OK')",
                       p / "motor.json") == "OK"
        for escenas in (["../fuera"], ["/absoluto"], ["a/../../fuera"], ["a\\b"], ["D:/externo"], [42], "ejemplo"):
            (p / "config.json").write_text(json.dumps(dict(regresion=dict(escenas=escenas))), encoding="utf-8")
            assert proceso("try:\n import regresion\nexcept ValueError: print('OK')\nelse: raise AssertionError('Aceptó ruta inválida')",
                           p / "motor.json") == "OK"


PRUEBAS = [(n, f) for n, f in globals().items() if n.startswith("a_") and callable(f)]
