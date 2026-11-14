"""Registro opcional de actores, piezas, montajes y símbolos de compatibilidad."""
from threading import RLock

from configuracion import cargar_extension


class Registro:
    def __init__(self):
        self.personajes, self.piezas, self.recetas = {}, {}, {}
        self.descripciones, self.ordenadores, self.exportados = {}, {}, {}

    @staticmethod
    def _agregar(tabla, nombre, valor):
        if nombre in tabla:
            raise ValueError(f"Componente ya registrado: {nombre!r}")
        tabla[nombre] = valor

    def personaje(self, nombre, clase):
        self._agregar(self.personajes, nombre, clase)

    def pieza(self, nombre, constructor):
        self._agregar(self.piezas, nombre, constructor)

    def receta(self, nombre, constructor, datos, ordenar=None):
        self._agregar(self.recetas, nombre, constructor)
        self.descripciones[nombre] = dict(datos)
        if ordenar is not None:
            self.ordenadores[nombre] = ordenar

    def exportar_modulo(self, modulo, privados=()):
        nombres = getattr(modulo, "__all__", [n for n in vars(modulo) if not n.startswith("_")])
        # Las fachadas históricas permiten que un módulo posterior reexporte el mismo nombre.
        self.exportados.update({n: getattr(modulo, n) for n in [*nombres, *privados]})

    def vaciar(self):
        for tabla in (self.personajes, self.piezas, self.recetas, self.descripciones, self.ordenadores, self.exportados):
            tabla.clear()


_REGISTRO = Registro()
_ESTADO = "pendiente"
_CERROJO = RLock()


def registro_actual():
    global _ESTADO
    with _CERROJO:
        if _ESTADO in ("listo", "cargando"):
            return _REGISTRO
        _ESTADO = "cargando"
        try:
            extension = cargar_extension("registro")
            if extension is not None:
                extension.registrar(_REGISTRO)
        except BaseException:
            _REGISTRO.vaciar()
            _ESTADO = "pendiente"
            raise
        _ESTADO = "listo"
        return _REGISTRO


def exportaciones():
    return dict(registro_actual().exportados)


def crear_pieza(nombre, *args, **kwargs):
    r = registro_actual()
    if nombre not in r.piezas:
        raise ValueError(f"Pieza no registrada: {nombre!r}")
    return r.piezas[nombre](*args, **kwargs)
