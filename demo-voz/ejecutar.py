"""Narrated demo: generates the voice with edge-tts (needs internet) and runs the normal production pipeline.

    python demo-voz/ejecutar.py            preview, 540x960 at 15 fps
    python demo-voz/ejecutar.py --final    1080x1920 at 30 fps
"""
import os
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = next(p for p in AQUI.parents if (p / "motor").is_dir())

if __name__ == "__main__":
    env = dict(os.environ, MOTOR_CONFIG="-", PYTHONPATH=str(RAIZ / "motor"))
    sys.exit(subprocess.call([sys.executable, str(RAIZ / "motor/producir.py"), str(AQUI), *sys.argv[1:]], env=env))
