# OPTIMIZATION LOG (beyond PROJECT_BLUEPRINT.md)

| # | Finding | Change | Why |
|---|---|---|---|
| 1 | Blender here is 5.2 (Grease Pencil v3, no `fcurves` on actions, EEVEE Next = GPU via GL/Vulkan, not CUDA/OptiX) | Code targets 5.x APIs (layered actions via `fcurves_of`); GPU detection reports nvidia-smi | Blueprint assumed 4.x |
| 2 | Line Art GP is CPU-recomputed every frame | Character outline = inverted-hull solidify (GPU-cheap, animates with rig); `add_lineart()` kept for static sets only | Speed + stable lines on moving characters |
| 3 | Mixamo needs an Adobe login | Body language is an authored NLA library (9 actions) driven by direction vectors, so ANY actor shares it (`actions_lib.py`) | No account needed, rig-agnostic |
| 4 | MPFB2 rig built without joint helpers scrambled every bone | `detailed_helpers=True` in `build_actor.py` | Real bug found by dumping bone positions |
| 5 | No viseme shape-keys downloadable | Face = bone offsets (brows, lids, cheeks, lips, jaw) in armature space, converted per rig; Rhubarb cues drive jaw+lips; auto blinks; eye look-at | Works on every actor, moves brows/lashes too |
| 6 | Per-frame CPU cost dominated render | Baked macro shape keys, removed subsurf, decimated shoes (28k verts) | ~15-20% faster frames |
| 7 | Photo skin textures turned olive when posterized | Texture kept, value/saturation lift only; bands come from lighting | Natural skin tones |
| 8 | Toon bands ignore light energy (clipped) | Night/dramatic moods also use scene exposure | Moods actually read dark |
| 9 | Clothes z-fight skin | 4 mm Displace "puff" on clothes | No skin speckles |
| 10 | Token cost | Director writes ONE ~1.5k-token JSON; reads ONE contact sheet; catalog manifest generated from disk (~700 tokens); voice/lipsync/compose all local | Episode cost ~4-6k tokens |
| 11 | Portability | `bootstrap_studio.py` downloads MPFB2 (sha256-checked), CC0 packs, Rhubarb, GSAP; vault rebuilt from JSON recipes; binaries gitignored | Repo stays tiny |
| 12 | Overlays | HTML5+GSAP rendered deterministically (seek per frame) in headless Chrome to transparent PNGs; subtitles via libass; BGM/SFX synthesized by FFmpeg | No Remotion install, no downloads, no licences |
| 13 | Render parallelism | Resumable chunked renders with N Blender workers | Resume after interruption; scales when GPU is free |

Measured: 1080p EEVEE frames ~0.6-0.85 s each on an RTX 3060 that was ALREADY ~75% busy with other apps (Steam/EA/NVIDIA overlay/Chrome);
an idle GPU should be markedly faster. Lever: `samples` in the shotlist (default 8), `--workers`.
Not done / future: Mixamo/CMU mocap import, true NLA retiming of walk to stride, hair physics, cloth, viseme shape-keys, Remotion.
