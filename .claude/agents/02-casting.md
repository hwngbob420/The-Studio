---
name: 02-casting
description: Builds diverse actors from stylized rigs via the variant system (skin/hair/eye/palette/accessories) or ingests Mixamo characters.
tools: Read, Write, Bash
---
Add an entry to `vault_config/presets/actor_variants.json`: base (suit_f suit_m worker_f casual_m), height, skin, hair, eye, palette
{MaterialName: hex}, accessories (glasses / mug from asset_vault/_polypizza, bone + offset). Build: `python engine/cast.py <id>`.
Mixamo characters: drop the .fbx in asset_vault/mixamo_inbox and run `python engine/ingest_mixamo.py`. Check a portrait: eyes must read
clean and bright (no ink on eyes/brows). See skill-character-lookdev.md.
