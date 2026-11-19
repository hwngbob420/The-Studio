# OPTIMIZATION LOG

## V2 (stylized-cinema overhaul) - what changed and why
V1 post-mortem: uncanny MPFB faces with smudged ink eyeliner, box buildings / sphere trees, frozen poses, UI cards over faces, flat light.

| # | V2 change | Why / evidence |
|---|---|---|
| 1 | MPFB2 retired. Characters = Quaternius CC0 rigged humans (via Poly Pizza, no login) + `actor_variants.json` (skin / hair / eye / palette / height / glasses / mug) | stylized proportions, no uncanny valley; 4 base rigs -> unlimited cast |
| 2 | Charismatic eyes: eyeball spheres with iris + catch-light shader, Eye bones for tracking, blink/squint/wide keys | eyes are the face; flat black eye patches replaced |
| 3 | Ink hull weighted by vertex group: brows/eyes/mouth get NO outline (eyes are separate un-inked meshes) | fixes the "smudged eye" bug in extreme close-ups |
| 4 | V2 shader: 3 warm bands (cool shadow / neutral mid / warm highlight) driven by HDRI + lights, soft band edges | replaces harsh 2-tone cel look |
| 5 | Sets built ONLY from real assets (KayKit buildings/roads/cars/furniture/trees, Poly Haven props, AmbientCG PBR surfaces, Poly Haven HDRI sky). `build_set_v2.py` contains no box/sphere builders on purpose | V1 box buildings and stick trees banned |
| 6 | 3-layer light: HDRI bounce + key sun + rim sun + soft fill area light; fast-GI ambient occlusion; flat contact-shadow blobs under feet; DoF f/2.4-2.8 on CloseUp/OTS focused on the speaker's eyes | rim separation, grounding, cinematic focus |
| 7 | Layered NLA acting: base clip (rig's native idle / walk / sit) + upper-body authored gestures (11 actions, quaternion, layer on top) + blinks every 3-5 s + eye look-at + Rhubarb visemes on a mouth card + emotes | no frozen poses; legs keep natural weight shift under gestures |
| 8 | Rule-of-thirds UI contract (`subject_zone`, `ui_safe_zone`): compiler lens-shifts the subject, `ui_layout.py` auto-places callouts, `contact_sheet_gen.py` draws UI + face boxes and exits 2 on overlap | UI can never cover a face; caught before any render |
| 9 | `ingest_mixamo.py`: inbox watcher; characters -> toon + ink + thumbnail; animations -> direction-based retarget onto the Studio rig -> `mx_*` NLA actions; registry + manifest | Adobe login stays with the human, everything after is automatic (smoke-tested with a synthetic FBX only: no real Mixamo file was available) |
| 10 | Bug fixes found by looking: Blender 5 creates shape keys at value 1.0; glTF import leaves 24 NLA tracks (characters lay down); native clips are quaternion so euler-authored actions were ignored; UV layer needed for the eye shader | each cost an iteration; all guarded now |

Known limits: faces are simple low-poly (expressive via eyes/brows/mouth card, no cheeks/teeth); sit pose is experimental; hands are blocky;
KayKit scale is toy-sized (rescaled per prop); Mixamo retarget ignores finger/twist; GPU is shared with other apps on this machine.

## V1 (kept for history)
MPFB2 + bone face rig, inverted-hull outline, procedural sets, GSAP overlays, FFmpeg master. See git history before the V2 commit.
