# Contributing to beatframe

Thanks for your interest! Small, focused pull requests are the easiest to review. Issues labelled **good first issue** are a good place to start.

## Set up

```sh
git clone https://github.com/grampass/beatframe.git
cd beatframe
python -m venv .venv
# activate it with the command for your shell
python -m pip install -r requirements-publico.txt
python motor/pruebas_motor.py
```

You also need FFmpeg and the system packages Manim requires ([installation guide](https://docs.manim.community/en/stable/installation.html)). The tests need no network and no speech service.

## Before opening a pull request

1. `python motor/pruebas_motor.py` must end with `TODO BIEN` ("all good"). CI runs the same command on Linux.
2. If you change drawing, timing or composition, also run `python ejemplo/ejecutar.py` and look at `ejemplo/revision/contacto.png`, the contact sheet. If the change is visible, attach a before/after image to the PR.
3. New behaviour needs a test. Look at `motor/pruebas_*.py`: each test is a plain function, registered in that file's `PRUEBAS` list.
4. Keep the core generic. `motor/` must not depend on any particular channel, brand or character set; project-specific things live in an external configuration loaded through `MOTOR_CONFIG`.

## Language

The code, API and messages are currently in Spanish. You can write issues and PRs in English or Spanish. New public names may be Spanish or English, but please add a short docstring. English aliases for the main API are a planned, welcome contribution.

## Style

- Python 3.11, standard library first. Ask in an issue before adding a dependency.
- Characters keep the same pieces in the same order on every frame (see `motor/personajes/base.py`). Change shapes by moving points, never by adding or removing pieces mid-video.
- Composition helpers place things in named zones (`Plano`), not at loose coordinates.

## Reporting bugs

Open an issue with the command you ran, the last lines of the output, your OS and Python version, and, if possible, the smallest `guion.json` + `escena.py` that reproduce the problem.
