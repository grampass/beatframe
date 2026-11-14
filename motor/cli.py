"""Orden `beatframe` del paquete instalado: lo mismo que `python motor/producir.py`.

    beatframe <carpeta> [--final | --choques | --beats b2-b4 | --crear-escena ...]
"""
import sys

import beatframe  # noqa: F401  (pone los módulos del motor en el path)


def main():
    import producir
    return producir.cli()


if __name__ == "__main__":
    sys.exit(main())
