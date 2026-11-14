"""Montajes y orden de capas suministrados por componentes registrados."""
from dataclasses import dataclass

from registro import registro_actual


@dataclass
class Montaje:
    nombre: str
    personaje: object
    capas: list
    escenario: object = None


RECETAS = registro_actual().descripciones


def aplicar_receta(escena, nombre):
    r = registro_actual()
    if nombre not in r.recetas:
        raise ValueError(f"Receta desconocida {nombre!r}; disponibles: {', '.join(RECETAS)}")
    anterior = getattr(escena, "_receta_actual", None)
    if anterior and anterior.nombre == nombre:
        return anterior
    datos = RECETAS[nombre]
    montaje, plano, sub_y = r.recetas[nombre](escena, nombre, datos)
    if anterior:
        escena.remove(*anterior.capas)
    escena.plano, escena.sub_y = plano, sub_y
    escena.add(*montaje.capas)
    escena.ambiente(datos.get("ambiente"))
    escena._receta_actual = montaje
    return montaje


def objetos_en_mesa(escena, montaje, *objetos, tocados=()):
    """Conserva pertenencia y contacto; el componente decide las capas particulares."""
    from manim import VGroup
    tocados = list(tocados)
    sueltos = [o for o in objetos if not any(o is t for t in tocados)]
    grupo = VGroup(*tocados, montaje.personaje) if tocados else montaje.personaje
    if tocados:
        grupo.contenedor = True
    escena.remove(*montaje.capas)
    ordenar = registro_actual().ordenadores.get(montaje.nombre)
    if ordenar is not None:
        capas = ordenar(montaje, sueltos, grupo)
    else:
        capas = [c for c in montaje.capas if c is not montaje.personaje] + [*sueltos, grupo]
    montaje.capas = capas
    escena.add(*capas)
    return montaje
