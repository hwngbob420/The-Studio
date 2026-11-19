# THE STUDIO - orchestrator rules
Local GPU cartoon film studio. You DIRECT; Python/Blender/FFmpeg do the work (0 tokens).
Flow: script -> 01-showrunner (episode_shotlist.json from vault_config/catalog_manifest.json) -> `python engine/produce.py <ep>`
 -> 04-cinematographer reads ONLY contact_sheet.jpg and patches JSON -> render -> 05-motion-editor master -> output_final.mp4.
Never write Blender code for an episode; extend engine/ or vault_config/ only if the catalog lacks something (then rerun catalog_gen).
Token budget per episode: manifest ~700 + shotlist ~1,500 + 1 contact sheet + 3 QA frames.
Agents: .claude/agents/01..05. Commands: /produce-scene /cast-actor /build-set /studio-doctor. Schema: .claude/skills/shotlist-schema.md
Facts: Blender 5.x EEVEE Next (GPU), actors = MPFB2 + Master Toon + inverted-hull ink, parallel resumable render.
Paths contain spaces: always quote. Heavy outputs (asset_vault, productions/*/render) are gitignored.
