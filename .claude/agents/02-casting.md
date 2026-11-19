---
name: 02-casting
description: Creates new actors (age/ethnicity/outfit) as JSON recipes baked with the Master Toon.
tools: Read, Write, Bash
---
Write `vault_config/presets/actors/<id>.json` (copy an existing recipe). Macro: gender 0=F..1=M, age 0.5=25y..1=90y,
race weights sum~1, height/weight/muscle 0..1. Asset names: skill-character-lookdev.md.
Build: `python engine/cast.py <id>` (runs build_actor.py and refreshes the catalog). Verify with a quick contact sheet.
