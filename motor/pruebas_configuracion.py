"""Pruebas de aislamiento y configuración opcional en procesos independientes."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

MOTOR = Path(__file__).resolve().parent


def proceso(codigo, manifiesto="-", *args):
    env = dict(os.environ, MOTOR_CONFIG=str(manifiesto), PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-c", codigo, *map(str, args)], cwd=MOTOR, env=env,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr or r.stdout
    return r.stdout.strip()


def c_sin_config_no_hay_voces_ni_politica():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        g = dict(id="PRUEBA", titulo="Ejemplo", curso="general", especialista="actor", concepto="Ejemplo",
                 beats=[dict(id="b1", personaje="actor", voz="es-ES-AlvaroNeural", texto="Una prueba.",
                             escenario="vacio", visual="Una forma se mueve.")])
        (p / "guion.json").write_text(json.dumps(g), encoding="utf-8")
        resultado = proceso('import json,sys; from contrato import VOCES; from validar import validar; '
                            'from pathlib import Path; e,a=validar(Path(sys.argv[1]),estricto=True); '
                            'print(json.dumps([VOCES,e,a,"manim" in sys.modules]))', "-", p)
        assert json.loads(resultado) == [{}, [], [], False], resultado


def c_config_mal_formada_no_se_oculta():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "motor.json").write_text('{"configuracion":"."}', encoding="utf-8")
        (p / "config.json").write_text('[]', encoding="utf-8")
        r = subprocess.run([sys.executable, "-c", "import configuracion"], cwd=MOTOR,
                           env=dict(os.environ, MOTOR_CONFIG=str(p / "motor.json")), capture_output=True)
        assert r.returncode != 0 and b"ValueError" in r.stderr, r.stderr


def c_config_preserva_prosodia_y_firma_archivos():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "motor.json").write_text('{"configuracion":"."}', encoding="utf-8")
        (p / "config.json").write_text(json.dumps(dict(voces={"actor":"voz-ejemplo"},
            prosodia={"actor":["-7%","-2Hz"]})), encoding="utf-8")
        codigo = ('import json; from contrato import argumentos_voz; from configuracion import archivos_configuracion; '
                  'from artefactos import sha256; print(json.dumps([argumentos_voz(dict(personaje="actor",texto="Hola")), '
                  '{str(p):sha256(p) for p in archivos_configuracion()}]))')
        a = json.loads(proceso(codigo, p / "motor.json"))
        assert a[0] == ["Hola", "voz-ejemplo", "-7%", "-2Hz"], a
        (p / "lexico.json").write_text('{"riesgo":{}}', encoding="utf-8")
        b = json.loads(proceso(codigo, p / "motor.json"))
        assert a[1] != b[1] and str(p / "lexico.json") in b[1], b


PRUEBAS = [(n, f) for n, f in globals().items() if n.startswith("c_") and callable(f)]
