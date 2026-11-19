# THE STUDIO (V2)

A film studio on your own PC. You write a script; it makes a 1080p 60fps stylized cartoon video with acting, lip-sync, camera moves,
real 3D sets, cinematic lighting, motion-graphic callouts and subtitles. Rendering is local and free.

## Use it in any project

```bash
git clone https://github.com/hwngbob420/The-Studio.git
cd The-Studio
python bootstrap_studio.py
```

The bootstrap downloads everything it needs (free, no logins, about 300 MB): characters, KayKit city/furniture/nature, Poly Haven props
and skies, AmbientCG textures, Rhubarb, then builds the cast, sets and animation library.
Needs: Blender 4.2+ (5.x tested), Python 3.10+, FFmpeg, Node.js, Chrome or Edge, a GPU.

## Make a video

```
/produce-scene productions/my_video  "Your script here..."
```
or copy `productions/showcase_v2/episode_shotlist.json`, edit it, then `python engine/produce.py productions/my_video`.
Stages: `--stage voice | compile | sheet | render | final`. Read `contact_sheet.jpg` first: orange boxes are text cards, green boxes are faces;
the command stops (exit 2) if a card would cover a face. The result is `productions/my_video/output_final.mp4`.

## Add Mixamo characters and animations (30 seconds, needs your free Adobe login)

1. Open https://www.mixamo.com and sign in.
2. Characters tab: pick one (Louise, Remy, AJ, Megan, Leonard...) -> Download -> Format **FBX Binary**, Pose **T-pose** -> Download.
3. Animations tab: pick moves (Talking, Shrugging, Sitting Tired, Drinking Coffee, Laughing...) -> Download -> FBX Binary, **Without Skin**, 30 fps.
4. Drop all the `.fbx` files into `asset_vault/mixamo_inbox/`.
5. Run `python engine/ingest_mixamo.py` (or `/ingest-mixamo`). Characters become actors; animations become `mx_<name>` clips you can use in
   `actions` of any shot. Add `--watch` to ingest automatically while you download.

## Add people and places

`/cast-actor "55 year old chef, warm, grey beard"` (a new colour/age/outfit variant of a hero rig, plus glasses/mug accessories).
`/build-set "rooftop bar at dusk"` (real assets only: no boxes, spheres or cylinders for buildings, trees or furniture).

Doctor: `/studio-doctor` or `python bootstrap_studio.py --doctor`.
See `OPTIMIZATION_LOG.md` (what V2 changed and why). All bundled assets are CC0 (Quaternius, KayKit, Poly Haven, AmbientCG); Rhubarb and Blender are open source.
