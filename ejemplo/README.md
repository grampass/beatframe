# Offline geometry example

Run `python ejemplo/ejecutar.py` from the distribution root. Add `--final` for full resolution. The script calls the regular production pipeline.

This example uses locally generated quiet tones and authored word cues. **It contains no spoken narration and does not contact a speech service.** The cues demonstrate scheduling and subtitles; they are not measured speech timings. To use narration in a new scene, supply real audio with matching word timings, or configure a supported speech provider.

The articulated unit and its manipulator are built from geometric primitives. The example moves a disk, changes the pointing pose and fills an indicator. No images or font files are bundled.
