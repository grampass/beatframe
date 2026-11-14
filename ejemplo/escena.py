"""Escena geométrica: un módulo, una pinza y un disco."""
import os
import sys
from pathlib import Path

os.environ["MOTOR_CONFIG"] = "-"
for padre in Path(__file__).resolve().parents:
    if (padre / "motor").is_dir():
        sys.path.insert(0, str(padre / "motor"))
        break
else:
    raise RuntimeError("Colocar el ejemplo junto a la carpeta motor")

from estudio import EscenaEstudio, Circle, VGroup, LEFT
from personajes.demo import Demo


class Ejemplo(EscenaEstudio):
    carpeta = Path(__file__).resolve().parent

    def construct(self):
        actor = Demo(pos=(-1.5, -2), escala=.85).conectar(self)
        pieza = Circle(.35, color="#E8BD6B", fill_opacity=.3).move_to([1.4, -.4, 0])
        pieza.importante = True
        grupo = VGroup(actor, pieza)
        grupo.contenedor = True
        self.add(grupo)
        self.hasta(self.g['b1']['ini'])
        self.play(actor.anim(**actor.alcanzar(1.4, -.4)), run_time=.4)
        self.play(pieza.animate.shift(LEFT * 1.2), actor.anim(**actor.alcanzar(.2, -.4)), run_time=1.2)
        self.fin_beat('b1')
        self.hasta(self.g['b2']['ini'])
        self.play(actor.anim(pose='senala'), run_time=.8)
        self.fin_beat('b2')
        self.hasta(self.g['b3']['ini'])
        self.play(actor.anim(carga=1.), run_time=1.2)
        self.fin_beat('b3')
