# THE STUDIO V2 - orchestrator rules
Local GPU stylized-cinema studio. You DIRECT; Python/Blender/FFmpeg do the work (0 tokens).
Flow: script -> 01-showrunner writes episode_shotlist.json from vault_config/catalog_manifest.json -> `python engine/produce.py <ep>`
 -> 04-cinematographer reads ONLY contact_sheet.jpg (UI boxes + face boxes drawn on it; exit code 2 = overlap) and patches JSON
 -> render -> 05-motion-editor master -> output_final.mp4.
IRON RULES (V2)
 1 Characters = Quaternius rigged CC0 bases + variants (vault_config/presets/actor_variants.json) or Mixamo drops (asset_vault/mixamo_inbox).
 2 Sets = REAL assets only (KayKit, Poly Haven, AmbientCG, HDRI). NEVER build houses/trees/cars/furniture from cubes/cylinders/spheres.
 3 Look = engine V2 toon (3-band warm) + ink hull that EXCLUDES eyes/brows/mouth + HDRI + key/fill/rim + DoF on OTS/CloseUp.
 4 Every actor is always alive: base clip (idle/walk/sit) + upper-body action + blinks + eye tracking + lip-sync. No frozen poses.
 5 UI contract: every shot declares subject_zone (left_third|center|right_third) and ui_safe_zone (right_third|top_left|none).
   Callouts carry NO x/y; they are auto-placed inside ui_safe_zone. Zero UI over faces - the contact sheet check enforces it.
Never write Blender code for an episode; extend engine/ or vault_config/ only if the catalog lacks something, then run engine/catalog_gen.py.
Token budget/episode: manifest ~800 + shotlist ~1,800 + 1 contact sheet + 3 QA frames.
Agents .claude/agents/01..05; commands /produce-scene /cast-actor /build-set /ingest-mixamo /studio-doctor; schema .claude/skills/shotlist-schema.md
Paths contain spaces: always quote. Heavy outputs (asset_vault, productions/*/render) are gitignored; bootstrap_studio.py rebuilds them.
