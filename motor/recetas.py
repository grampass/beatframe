"""Montajes y orden de capas suministrados por componentes registrados."""
from dataclasses import dataclass, field

from registro import registro_actual


@dataclass
class Montaje:
    nombre: str
    personaje: object
    capas: list
    escenario: object = None
    opciones: dict = field(default_factory=dict)


RECETAS = registro_actual().descripciones


def opciones_receta(escena, nombre, explicitas=None):
    """Ajustes del escenario para esta receta: los del guion («ajustes_receta»: {receta: {...}}) y encima los de la
    llamada. Así un ajuste decidido en el guion (p. ej. un objeto frío) no depende de acordarse en cada escena."""
    guion = getattr(getattr(escena, "g", None), "ajustes_receta", None) or {}
    return {**guion.get(nombre, {}), **(explicitas or {})}


def aplicar_receta(escena, nombre, **opciones):
    r = registro_actual()
    if nombre not in r.recetas:
        raise ValueError(f"Receta desconocida {nombre!r}; disponibles: {', '.join(RECETAS)}")
    opciones = opciones_receta(escena, nombre, opciones)
    anterior = getattr(escena, "_receta_actual", None)
    if anterior and anterior.nombre == nombre and anterior.opciones == opciones:
        return anterior
    datos = RECETAS[nombre]
    try:
        montaje, plano, sub_y = r.recetas[nombre](escena, nombre, datos, **opciones)
    except TypeError as e:
        if not opciones:
            raise
        raise ValueError(f"La receta {nombre!r} no acepta los ajustes {sorted(opciones)}: {e}") from e
    montaje.opciones = dict(opciones)
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
