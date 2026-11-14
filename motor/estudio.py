"""Fachada compatible: núcleo genérico y exportaciones de componentes registrados."""
import json
import os
from pathlib import Path

import numpy as np
from manim import *
from manim.constants import CapStyleType, LineJointType

from plano import Plano, COMPOSICIONES
from nucleo import *
from nucleo import _opacidades
from piezas.basicas import *
from personajes.base import Personaje
from registro import exportaciones as _exportaciones

globals().update(_exportaciones())

from piezas.inserto import *
from piezas.objetos import *
from recetas import RECETAS, aplicar_receta
