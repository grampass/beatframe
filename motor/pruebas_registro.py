"""Comprueba el registro genérico con extensiones mínimas ajenas al proyecto."""
import json
import tempfile
from pathlib import Path

from pruebas_configuracion import proceso


def r_sin_config_la_fachada_no_registra_componentes():
    r = json.loads(proceso('import json; import estudio; from registro import registro_actual; '
                          'r=registro_actual(); print(json.dumps([len(r.personajes),len(r.piezas),len(r.recetas)]))'))
    assert r == [0, 0, 0], r


def r_extension_monta_una_vez_y_exporta():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "motor.json").write_text('{"configuracion":"."}', encoding="utf-8")
        (p / "config.json").write_text(json.dumps(dict(extensiones=dict(registro=str(p / "extension.py")))), encoding="utf-8")
        (p / "extension.py").write_text('''from types import SimpleNamespace, ModuleType
def registrar(r):
    modulo = ModuleType("demo_local")
    modulo.marca = 37
    r.exportar_modulo(modulo)
    r.personaje("actor", object)
    r.pieza("pieza", lambda valor: valor+1)
    def construir(s,n,datos):
        s.contador += 1
        return SimpleNamespace(nombre=n,capas=["capa"],personaje="actor"), "plano", 2.5
    r.receta("mesa",construir,dict(ambiente=None))
''', encoding="utf-8")
        codigo = '''import json
from registro import crear_pieza, exportaciones
from recetas import aplicar_receta
class Escena:
    contador=0
    def add(self,*a): pass
    def remove(self,*a): pass
    def ambiente(self,a): pass
s=Escena(); a=aplicar_receta(s,"mesa"); b=aplicar_receta(s,"mesa")
print(json.dumps([a is b,s.contador,s.sub_y,exportaciones()["marca"],crear_pieza("pieza",4)]))
'''
        assert json.loads(proceso(codigo, p / "motor.json")) == [True, 1, 2.5, 37, 5]


def r_extension_fallida_no_deja_registro_parcial():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "motor.json").write_text('{"configuracion":"."}', encoding="utf-8")
        (p / "config.json").write_text(json.dumps(dict(extensiones=dict(registro=str(p / "extension.py")))), encoding="utf-8")
        (p / "extension.py").write_text('def registrar(r):\n r.pieza("parcial",object)\n raise RuntimeError("fallo controlado")\n', encoding="utf-8")
        codigo = '''import json
import registro
errores=[]
for _ in range(2):
    try: registro.registro_actual()
    except RuntimeError as e: errores.append(str(e))
print(json.dumps([errores,len(registro._REGISTRO.piezas)]))
'''
        assert json.loads(proceso(codigo, p / "motor.json")) == [["fallo controlado"]*2, 0]


PRUEBAS = [(n, f) for n, f in globals().items() if n.startswith("r_") and callable(f)]
