# Narrated demo

`python demo-voz/ejecutar.py` generates an English voice with `edge-tts` (an external service: it needs internet), measures every word, checks pronunciation if `faster-whisper` is installed, checks the composition at 15 and 30 fps, and renders `demo-voz/vista-previa.mp4`. Add `--final` for 1080×1920.

Read `escena.py` next to `guion.json`: every action is anchored to a spoken word with `self.en(beat, word, ...)`. Change a sentence in `guion.json` and run again: the voice, subtitles and animation stay in sync without touching a single time value.

The robot (`motor/personajes/demo.py`) is drawn from primitives only. Its poses are `reposo`, `senala`, `explica`, `mira_abajo` and `jala`. Its expressions are `alegre`, `sorpresa`, `duda`, `concentrada` and `fastidio`. `carga` (0–1) lights its antenna and chest meter.
