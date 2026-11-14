"""Pruebas del flujo y su recuperación. Red y render simulados; WAV y caché de voz reales."""
import asyncio
import contextlib
import hashlib
import io
import os
import json
import tempfile
import wave
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from artefactos import Bloqueo, CacheEtapas, escribir_json, firma, leer_json
from contrato import argumentos_voz
from flujo import eventos_reutilizados, preparar_revision, vigencia_visual
import producir
import tts
from validar import validar


def fixture(p):
    p.mkdir(exist_ok=True, parents=True)
    g = dict(id="FLUJO", titulo="PRUEBA", curso="termodinamica", especialista="demo", concepto="Prueba",
             estado="prueba", formato="corto", simplificaciones=["Prueba"],
             pruebas=dict(mudo=True, dibujo=True, experto=True),
             beats=[dict(id=f"b{i}", personaje="demo", voz="voz-prueba", escenario="lamina", texto="Una prueba.",
                         visual="Un objeto visible permanece en el centro.") for i in range(1, 5)])
    escribir_json(p / "guion.json", g)
    (p / "escena.py").write_text("class Flujo(EscenaEstudio):\n    pass\n", encoding="utf-8")
    (p / "audio").mkdir(exist_ok=True)
    return g


def wav(p):
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
        w.writeframes(b"\0\0" * 1600)
    return [dict(w="prueba", t=0.0, d=0.1)]


async def voz(texto, nombre, rate, pitch, destino):
    return wav(destino)


def call_main(p, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return producir.main(p, **kw)


def f_json_mal_formado_y_tipos():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); fixture(p)
        for x in ([], {"beats": [None]}, {"beats": "texto"}):
            escribir_json(p / "guion.json", x)
            assert validar(p)[0], x


def f_tiempos_vacios_sin_traceback():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); g = fixture(p)
        for b in g["beats"]:
            wav(p / "audio" / (b["id"] + ".mp3"))
        escribir_json(p / "audio" / "tiempos.json", {b["id"]: [] for b in g["beats"]})
        assert any("tiempos" in e for e in validar(p, con_audio=True)[0])


def f_guion_invalido_bloquea_final_antes_de_voz():
    with tempfile.TemporaryDirectory() as d:
        p=Path(d); g=fixture(p); g['beats'][0]['cola']=-1
        escribir_json(p/'guion.json',g)
        with patch.object(producir,'correr',side_effect=AssertionError('No debe generar voz ni renderizar')):
            assert call_main(p,final=True)==1
        assert leer_json(p/'revision/resumen.json')['entrega_actual'] is None





def f_bloqueo_excluye_segunda_ejecucion():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "lock"
        with Bloqueo(p):
            try:
                with Bloqueo(p):
                    raise AssertionError("Dos escritores entraron")
            except RuntimeError:
                pass
        with Bloqueo(p):
            pass


def f_cache_verifica_salida_no_solo_nombre():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); out = p / "v.mp4"; out.write_bytes(b"original")
        c = CacheEtapas(p / "cache.json"); c.guardar("base", "firma", [out])
        assert c.vigente("base", "firma")
        assert not c.vigente("base", "otra")
        out.write_bytes(b"modificado")
        assert not c.vigente("base", "firma")
        escribir_json(p / "cache.json", {"version": 1, "etapas": []})
        assert not CacheEtapas(p / "cache.json").vigente("base", "firma")


def f_tts_reanuda_y_repara_audio_corrupto():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); fixture(p); llamadas = []
        async def fallo(texto, nombre, rate, pitch, destino):
            llamadas.append(destino.name)
            if len(llamadas) == 2:
                raise RuntimeError("servicio interrumpido")
            return wav(destino)
        with patch.object(tts, "decir", fallo), contextlib.redirect_stdout(io.StringIO()):
            try:
                asyncio.run(tts.main(p))
            except RuntimeError:
                pass
        assert leer_json(p / "audio" / "huellas.json").get("b1")
        assert leer_json(p / "audio" / "cache.json").get("b1")
        with patch.object(tts, "decir", side_effect=voz) as m, contextlib.redirect_stdout(io.StringIO()):
            r = asyncio.run(tts.main(p))
            assert m.call_count == 3 and r["reutilizados"] == ["b1"], r
        with patch.object(tts, "decir", side_effect=AssertionError("La caché no llama a la red")), contextlib.redirect_stdout(io.StringIO()):
            assert len(asyncio.run(tts.main(p))["reutilizados"]) == 4
        (p / "audio" / "b1.mp3").write_bytes(b"")
        with patch.object(tts, "decir", side_effect=voz) as m, contextlib.redirect_stdout(io.StringIO()):
            r = asyncio.run(tts.main(p))
            assert m.call_count == 1 and r["generados"] == ["b1"], r


def f_tts_comprobar_no_usa_red():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); fixture(p)
        with patch.object(tts, "decir", side_effect=AssertionError("No debe llamar a la red")):
            try:
                asyncio.run(tts.main(p, solo_comprobar=True))
            except ValueError:
                return
        raise AssertionError("Aceptó audio ausente")


def f_revision_no_se_revalida_sola():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); (p / "revision").mkdir()
        a, b = "a" * 64, "b" * 64
        assert preparar_revision(p, a) == "pendiente"
        f = p / "revision" / "revision-visual.md"
        f.write_text(f.read_text(encoding="utf-8").replace("- Revisó:", "- Revisó: Prueba").replace("[ ]", "[x]"), encoding="utf-8")
        assert vigencia_visual(p, a) == "declarada vigente por autor"
        antes = f.read_bytes()
        assert preparar_revision(p, b) == "desactualizada"
        assert f.read_bytes() == antes, "No se sobrescribe la revisión del autor"


def f_publicado_no_se_toca():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); fixture(p)
        (p / "README.md").write_text("- **Rol:** publicado · finalizado", encoding="utf-8")
        assert call_main(p) == 1
        assert not (p / "revision").exists()


def f_eventos_conservan_marcas_reales():
    a = {"efectos": [dict(nombre="clic", t=1.0, db=-30)]}
    r = {"efectos": [dict(nombre="clic", t=1.033, db=-30)]}
    n = {"efectos": [dict(nombre="clic", t=1.0, db=-22)]}
    e = eventos_reutilizados(a, r, n)
    assert e["efectos"][0] == dict(nombre="clic", t=1.033, db=-22)
    n["efectos"][0]["t"] = 2
    assert eventos_reutilizados(a, r, n) is None


class Simulador:
    """Aísla el orquestador; las pruebas de medios reales se ejecutan aparte."""
    def __init__(self, p):
        self.p, self.llamadas, self.bloquear, self.cambiar = p, [], False, False

    def deps(self, p):
        return dict(guion=leer_json(p / "guion.json"), escena=(p / "escena.py").read_text())

    def correr(self, cmd, cwd=None, env=None):
        cmd = [str(c) for c in cmd]
        if cmd[1].endswith("tts.py"):
            self.llamadas.append("voz-comprobar" if "--comprobar" in cmd else "voz")
            return 0, "voz ya preparada"
        if cmd[1].endswith("revisar.py"):
            self.llamadas.append("hojas")
            out = Path(cmd[6]); out.mkdir(parents=True)
            (out / "contacto.png").write_bytes(b"hoja simulada")
            return 0, "hojas"
        assert "manim" in cmd, cmd
        previo = env.get("SOLO_CHOQUES") == "1"
        self.llamadas.append("previo" if previo else "render")
        out = Path(env["REVISION_DIR"])
        escribir_json(out / "choques.json", dict(hallazgos=[dict(texto="solape", beats=["b1"])] if self.bloquear else [], muestras=[]))
        escribir_json(out / "tiempos-escena.json", dict(retrasos=[]))
        plan = leer_json(self.p / "sonido.json", {})
        escribir_json(out / "sonido-eventos.json", dict(ambientes=[], pistas=[], efectos=plan.get("efectos", [])))
        if not previo:
            media = Path(cmd[cmd.index("--media_dir") + 1]) / "videos" / "escena" / "960p15"
            media.mkdir(parents=True); (media / "Flujo.mp4").write_bytes(b"video simulado")
            if self.cambiar:
                (self.p / "escena.py").write_text("class Nueva(EscenaEstudio):\n    pass\n")
        return 0, "escena"

    def mezclar(self, fuente, salida, g, ruta, **kw):
        self.llamadas.append("mezcla")
        salida.write_bytes(b"mezcla" + Path(ruta).read_bytes())
        escribir_json(salida.with_suffix(".sonido.json"), dict(prueba=True))
        return dict(pico_acompanamiento=0.01)


def simular(p, s, **kw):
    with patch.object(producir, "correr", s.correr), patch.object(producir, "dependencias", s.deps), \
         patch.object(producir, "comprobar_video", return_value=dict(video=3, audio=3)), \
         patch("sonido.mezclar", s.mezclar):
        return call_main(p, **kw)


def audio_fixture(p, g):
    escribir_json(p / "audio" / "tiempos.json", {b["id"]: wav(p / "audio" / (b["id"] + ".mp3")) for b in g["beats"]})


def f_composicion_bloquea_render_y_choques_no_genera_voz():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); g = fixture(p); audio_fixture(p, g)
        s = Simulador(p); s.bloquear = True
        assert simular(p, s) == 1 and "render" not in s.llamadas
        s.llamadas.clear()
        assert simular(p, s, solo_choques=True) == 1
        assert "voz-comprobar" in s.llamadas and "voz" not in s.llamadas


def f_etapas_reutilizadas_y_ganancia_sin_render():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); g = fixture(p); audio_fixture(p, g)
        escribir_json(p / "sonido.json", dict(efectos=[dict(nombre="clic", t=0.1, db=-30)]))
        s = Simulador(p)
        assert simular(p, s) == 0
        assert simular(p, s) == 0
        assert s.llamadas.count("render") == s.llamadas.count("hojas") == s.llamadas.count("mezcla") == 1, s.llamadas
        escribir_json(p / "sonido.json", dict(efectos=[dict(nombre="clic", t=0.1, db=-22)]))
        assert simular(p, s) == 0
        assert s.llamadas.count("render") == s.llamadas.count("hojas") == 1, s.llamadas
        assert s.llamadas.count("mezcla") == 2, s.llamadas
        g["beats"][0]["visual"] += " Cambia la escena."
        escribir_json(p / "guion.json", g)
        assert simular(p, s) == 0 and s.llamadas.count("render") == 2
        assert leer_json(p / "revision" / "revision-vigencia.json")["visual"] == "desactualizada"


def f_cambio_concurrente_no_promueve_ni_borra_entrega():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); g = fixture(p); audio_fixture(p, g)
        (p / "vista-previa.mp4").write_bytes(b"entrega anterior")
        s = Simulador(p); s.cambiar = True
        assert simular(p, s) == 1
        assert (p / "vista-previa.mp4").read_bytes() == b"entrega anterior"
        assert leer_json(p / "revision" / "resumen.json")["entrega_actual"] is None
        assert not leer_json(p / "revision" / "cache-etapas.json", {}).get("etapas"), "No confirmar resultados de entradas mezcladas"


def f_ambiente_diferido_y_retraso_de_grupo():
    from manim import AnimationGroup, Scene, Wait
    from nucleo import EscenaEstudio
    from sonido import PistaSonora
    class S(EscenaEstudio):
        def setup(self):
            pass
    s = S(); s._sonora = PistaSonora(SimpleNamespace(total=8.0), True)
    s.renderer.time = 0
    s.ambiente("aire")
    anim = s.enfocar_anim(ambiente=None, run_time=1)
    assert s._sonora.ambientes[0]["hasta"] == 8, "Se cortó al construir, antes de esperar"
    grupo = AnimationGroup(Wait(1), anim, lag_ratio=1, run_time=4)
    s.renderer.time = 0.5
    with patch.object(Scene, "play"):
        s.play(grupo)
    assert abs(s._sonora.ambientes[0]["hasta"] - 2.5) < 1e-6, s._sonora.ambientes


def f_callar_corta_ambiente_explicito_sin_borrar_futuro():
    from sonido import PistaSonora
    p = PistaSonora(SimpleNamespace(total=8.0), True)
    p.ambiente("aire", 0, hasta=4)
    p.ambiente("aire", 6, hasta=8)
    p.callar(2)
    assert [(a["desde"], a["hasta"]) for a in p.ambientes] == [(0, 2), (6, 8)]


def f_inserto_en_movimiento_se_revisa_sin_dibujar():
    from manim import Text, RIGHT, linear, tempconfig
    from nucleo import EscenaEstudio, FUENTE
    import choques
    class S(EscenaEstudio):
        def setup(self):
            self.g = SimpleNamespace(palabras=[], beats=[dict(id="b1", ini=0, fin=2)])
            self._registro, self._hud = choques.Registro(), []
            self.next_section(skip_animations=True)
        def construct(self):
            fijo = Text("fijo", font=FUENTE, font_size=24)
            movil = Text("movil", font=FUENTE, font_size=24).shift(-RIGHT * 2)
            self.add(fijo, movil)
            self.play(movil.animate.shift(RIGHT * 4), run_time=1, rate_func=linear)
    with patch.dict(os.environ, {"SOLO_CHOQUES": "1"}), tempconfig(dict(dry_run=True, write_to_movie=False, save_last_frame=False,
                                                                      progress_bar="none", verbosity="ERROR")):
        s = S(skip_animations=True)
        with patch.object(s.camera, "capture_mobjects", side_effect=AssertionError("La comprobación no debe rasterizar")):
            s.render()
        hs = list(s._registro.vistos.values())
        assert any(h["tipo"] == "solape" and 0 < h["t"] < 1 for h in hs), hs


def f_receta_conserva_capas_y_no_duplica():
    from recetas import aplicar_receta
    from personajes.demo import Demo
    from pruebas_soporte import registro_demo
    s=SimpleNamespace(mobjects=[])
    s.add=lambda *m:s.mobjects.extend(m)
    s.remove=lambda *m:[s.mobjects.remove(x) for x in m]
    s.ambiente=lambda n:None
    with registro_demo():
        r=aplicar_receta(s,'demostracion')
        assert isinstance(r.personaje,Demo) and s.sub_y==3.6
        assert s.mobjects == r.capas
        antes=len(s.mobjects)
        assert aplicar_receta(s,'demostracion') is r and len(s.mobjects)==antes
        try: aplicar_receta(s,'desconocida')
        except ValueError: return
        raise AssertionError('Aceptó receta desconocida')


def f_generador_receta_y_contrato_compartido():
    from generar_escena import crear
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); g = fixture(p)
        (p / "escena.py").unlink()
        g["receta"] = "demostracion"
        g["beats"][0].update(composicion="mesa", ambiente=None)
        escribir_json(p / "guion.json", g)
        e, a = validar(p)
        assert not e and not any("campo(s) desconocido" in x for x in a)
        from pruebas_soporte import registro_demo
        with registro_demo():
            f = crear(p)
        s = f.read_text(encoding="utf-8")
        assert "aplicar_receta(self, 'demostracion')" in s and "pendiente_animar = True" in s


def f_pista_propia_baja_bajo_voz_y_conserva_cierre():
    import numpy as np
    import subprocess
    from sonido import PistaSonora, leer_audio, mezclar
    from pruebas_encuadre import _wav, _mp4
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        video, musica = p / "v.mp4", p / "m.wav"
        _mp4(video, 3, 3); _wav(musica, 2.5, frec=660, amp=0.6)
        g = SimpleNamespace(total=3.0, beats=[dict(palabras=[dict(t=1.0, d=0.6)])])
        resultados = []
        for atenuar in (False, True):
            plan = p / "plan.json"; salida = p / f"mezcla-{atenuar}.mp4"
            sonora = PistaSonora(g, True); sonora.archivo(musica, 0.3, atenuar=atenuar); sonora.guardar(plan)
            mezclar(video, salida, g, plan)
            resultados.append(leer_audio(salida))
        sin, con = resultados
        voz_sin = np.sqrt(np.mean(sin[round(1.15*48000):round(1.45*48000)]**2))
        voz_con = np.sqrt(np.mean(con[round(1.15*48000):round(1.45*48000)]**2))
        assert voz_con < voz_sin * 0.5, (voz_con, voz_sin)
        a = slice(round(2.2*48000), round(2.6*48000))
        assert np.sqrt(np.mean((sin[a]-con[a])**2)) < 0.01, "Se atenuó el cierre sin voz"


def f_pista_de_plan_se_valida_aun_sin_mezcla():
    from sonido import PistaSonora
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); escribir_json(p / "sonido.json", dict(pistas=[dict(archivo="ausente.wav", en=0)]))
        try:
            PistaSonora(SimpleNamespace(total=3.0), False).cargar(p / "sonido.json")
        except ValueError:
            return
        raise AssertionError("Aceptó la pista inexistente")





def f_mezcla_conserva_fotogramas_y_ambos_flujos():
    import subprocess
    from pruebas_encuadre import _mp4
    from sonido import PistaSonora, duraciones_video, mezclar
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); v, salida = p / "v.mp4", p / "s.mp4"
        _mp4(v, 2.133, 2.133)
        g = SimpleNamespace(total=3.0, beats=[])
        sonora = PistaSonora(g, True); sonora.efecto("clic", 0.3); sonora.guardar(p / "plan.json")
        mezclar(v, salida, g, p / "plan.json")
        def frames(r):
            return subprocess.check_output(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                             "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(r)], text=True).strip()
        assert frames(v) == frames(salida), "La mezcla quitó fotogramas al copiar el video"
        antes, despues = duraciones_video(v), duraciones_video(salida)
        assert abs(antes["video"] - despues["video"]) < 0.02 and abs(despues["video"] - despues["audio"]) < 0.1


def f_cambiar_receta_retira_capas_anteriores():
    from recetas import aplicar_receta
    from pruebas_soporte import registro_demo
    s=SimpleNamespace(mobjects=[])
    s.add=lambda *m:s.mobjects.extend(m)
    s.remove=lambda *m:[s.mobjects.remove(x) for x in m]
    s.ambiente=lambda n:None
    with registro_demo() as r:
        r.receta('segunda',r.recetas['demostracion'],dict(personaje='demo',ambiente=None))
        anterior=aplicar_receta(s,'demostracion')
        nuevo=aplicar_receta(s,'segunda')
        assert s.mobjects == nuevo.capas
        assert not any(c is v for c in anterior.capas for v in s.mobjects)


def f_parametros_invalidos_tienen_diagnostico_temprano():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        for k, v in (("cola", -1), ("cola", float("nan")), ("rate", 8), ("claves", [])):
            g = fixture(p); g["beats"][0][k] = v
            (p / "guion.json").write_text(json.dumps(g), encoding="utf-8")
            assert validar(p)[0], (k, v)


def f_actualizar_motor_invalida_mezcla_aunque_el_video_sea_identico():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); g = fixture(p); audio_fixture(p, g)
        escribir_json(p / "sonido.json", dict(efectos=[dict(nombre="clic", t=0.1, db=-30)]))
        s = Simulador(p)
        assert simular(p, s) == 0
        original_deps = s.deps
        s.deps = lambda carpeta: dict(original_deps(carpeta), version_motor="otra")
        assert simular(p, s) == 0
        assert s.llamadas.count("render") == s.llamadas.count("mezcla") == s.llamadas.count("hojas") == 2, s.llamadas


def f_mezcla_fallida_no_se_confirma_en_cache():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); g = fixture(p); audio_fixture(p, g)
        escribir_json(p / "sonido.json", dict(efectos=[dict(nombre="clic", t=0.1, db=-30)]))
        s = Simulador(p)
        with patch.object(producir, "correr", s.correr), patch.object(producir, "dependencias", s.deps), \
             patch.object(producir, "comprobar_video", side_effect=[dict(video=3, audio=3), ValueError("mezcla truncada")]), \
             patch("sonido.mezclar", s.mezclar):
            assert call_main(p) == 1
        assert not leer_json(p / "revision" / "cache-etapas.json", {}).get("etapas")
        assert simular(p, s) == 0 and s.llamadas.count("mezcla") == 2


PRUEBAS = [("flujo · " + n[2:].replace("_", " "), f) for n, f in globals().copy().items() if n.startswith("f_") and callable(f)]
