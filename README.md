# beatframe

**Write a script. Get a narrated, word-synced vertical animation.**

![Narrated demo: a small robot reacts on each spoken word](https://raw.githubusercontent.com/grampass/beatframe/main/docs/demo-voice.gif)

▶ [Watch the demo with sound (MP4, 21 s)](https://github.com/grampass/beatframe/blob/main/docs/demo-voice.mp4) · [Español](README.es.md)

In a timeline editor, every animation is pinned to a time. Change one sentence of the narration and everything after it drifts. In beatframe, animations are pinned to **words**: "on *push*, the ball rolls". The voice is generated (or supplied) with word timings, and the scene waits for each word, so it stays in sync when the text changes.

```python
self.en("b3", "push", ball.animate.shift(RIGHT), robot.anim(pose="explica"), run_time=0.9)
self.en("b4", "charge", robot.anim(carga=1.0), run_time=1.2)
```

It is built on [Manim](https://www.manim.community/) and aimed at short vertical explainers (9:16).

## What it does

- **Word-anchored timing.** `self.en(beat, word, *animations)` waits for the word and fits the animations in the time left before the beat ends. If they do not fit, it tells you how late you are and suggests a word where they would fit.
- **Subtitles from the voice.** Word timings drive karaoke-style subtitles and the character's mouth.
- **Automatic review before rendering.** A dry run, without drawing, checks overlapping text, text that is too small, crowded screens and safe areas, at both 15 and 30 fps. A late animation or an overlap stops the render and shows you where it is.
- **Review sheets.** Every render writes contact sheets: the last frame of each beat, plus safe-area overlays for the main vertical platforms.
- **Pronunciation check (optional).** A local speech recognizer listens to every generated sentence and flags words that came out wrong, before anyone watches the video.
- **Resumable stages.** Voice, checks, render, mix and sheets are cached by input hash. A run refuses to deliver if its sources change halfway.
- **Characters as state.** A character is a set of poses plus a drawing function. `Demo`, the robot above, is built from primitives only (no images or fonts) and is the template for your own.

## Quick start

Tested with Python 3.11 on Windows; the tests also run on Linux in CI. Install FFmpeg and the system packages [Manim needs](https://docs.manim.community/en/stable/installation.html), then:

```sh
python -m venv .venv
# activate it with the command for your shell
python -m pip install -r requirements-publico.txt
python motor/pruebas_motor.py        # ~1 minute, no network
python ejemplo/ejecutar.py           # offline example: tones instead of a voice
python demo-voz/ejecutar.py          # the narrated demo above (needs internet for the voice)
```

Each run writes `vista-previa.mp4` (540×960, 15 fps) and review sheets in the folder's `revision/`. Add `--final` for 1080×1920 at 30 fps.

## Make your own scene

1. **Script:** copy `demo-voz/guion.json`. One beat per sentence: `id`, `personaje`, `voz` (an [edge-tts](https://github.com/rany2/edge-tts) voice name), `texto`, `escenario`, `visual`. Set `"idioma"` to the language of the script.
2. **Scene:** copy `demo-voz/escena.py`. Subclass `EscenaEstudio`, add your objects, and anchor each action to a word with `self.en(...)`.
3. **Produce:** `python motor/producir.py <folder>`. Use `--choques` to run only the checks, which takes seconds to minutes depending on length.

`python motor/producir.py <folder> --crear-escena` writes a scene skeleton from the script. It is a draft to complete, not a finished animation.

## How it works

```
guion.json ─► voice + word timings ─► pronunciation check ─► dry run at 15 and 30 fps (composition, timing)
           ─► render ─► audio coverage and format check ─► review sheets ─► vista-previa.mp4 / final.mp4
```

## Honest limits

- The API and the messages are in **Spanish** (`escena`, `guion`, `hasta`, `fin_beat`…). English aliases are a welcome first contribution.
- Speech uses `edge-tts`, an external service: the narrated demo needs internet. The offline example and the tests do not.
- The composition checks sample the animation; they do not certify every pixel, the science or the editing. Watch the result.
- Windows is the tested platform; Linux runs the test suite in CI; macOS is untested. Two tests need LaTeX (Manim numbers).
- Not on PyPI yet: clone the repository and run from its root.

## Configuration

Without a manifest the toolkit uses neutral defaults: no assigned voices and no registered scene recipes. `MOTOR_CONFIG=-` explicitly disables extensions, and the examples and tests use this mode. To extend it, point `MOTOR_CONFIG` to a JSON manifest `{"configuracion": "<dir>"}`, whose `config.json` may define `voces`, `prosodia`, `visual`, `rutas` and `extensiones`. Extensions are trusted Python code, so load only files you control.

The pronunciation check needs `python -m pip install -r requirements-voz.txt` (faster-whisper; the first run downloads a model). Without it, production continues and warns.

## Contributing

Issues and pull requests are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md) and the issues labelled **good first issue**. Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

MIT, see [LICENSE](LICENSE). Dependencies and external services keep their own licenses and terms.
