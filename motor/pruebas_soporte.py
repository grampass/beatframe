"""Componentes ficticios y contexto aislado para las pruebas genéricas."""
from contextlib import contextmanager
from unittest.mock import patch

from manim import Circle, Rectangle, VGroup
from personajes.demo import Demo


@contextmanager
def registro_demo():
    import registro
    import recetas
    from plano import Plano
    r = registro.Registro()
    def construir(escena, nombre, datos):
        actor = Demo(pos=(-1, -2))
        fondo = Rectangle(width=8, height=12).set_opacity(0)
        return recetas.Montaje(nombre, actor, [fondo, actor]), Plano("mesa"), 3.6
    r.personaje("demo", Demo)
    r.pieza("mano_inserto", lambda punta: VGroup(Circle(.12).move_to([*punta, 0])))
    r.receta("demostracion", construir, dict(personaje="demo", ambiente="laboratorio"))
    with patch.object(registro, "_REGISTRO", r), patch.object(registro, "_ESTADO", "listo"), \
         patch.object(recetas, "RECETAS", r.descripciones):
        yield r
