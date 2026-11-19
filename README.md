# THE STUDIO

A film studio on your own PC. You write a script; it makes a 1080p 60fps cartoon video with acting, lip-sync,
camera moves, lighting, motion-graphic callouts and subtitles. Rendering is local and free.

## Use it in any project (3 commands)

```bash
git clone https://github.com/hwngbob420/The-Studio.git
cd The-Studio
python bootstrap_studio.py
```

`bootstrap_studio.py` downloads everything open-source it needs (about 700 MB, once) and builds the cast and sets.
Needs: Windows/Mac/Linux, Blender 4.2+ (5.x tested), Python 3.10+, FFmpeg, Node.js, Chrome or Edge, a GPU.

## Make a video

Open the folder in Claude Code and type:

```
/produce-scene productions/my_video  "Your script here..."
```

Or by hand: write `productions/my_video/episode_shotlist.json` (copy `productions/showcase_v1`), then

```bash
python engine/produce.py productions/my_video
```

Stages: `--stage voice | compile | sheet | render | final`. Look at `contact_sheet.jpg` before the long render.
The result is `productions/my_video/output_final.mp4`.

## Add people and places

`/cast-actor "55 year old chef, warm, grey beard"` and `/build-set "rooftop bar at dusk"`.

## Doctor

`/studio-doctor` or `python bootstrap_studio.py --doctor`

See `OPTIMIZATION_LOG.md` for what was improved beyond the blueprint and `PROJECT_BLUEPRINT.md` for the original spec.
All bundled assets are CC0 (MakeHuman, Poly Haven); Rhubarb, MPFB2 and Blender are open source.
