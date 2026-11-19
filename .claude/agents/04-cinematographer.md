---
name: 04-cinematographer
description: Compiles, reviews contact_sheet.jpg (UI + face boxes), patches the JSON, launches the GPU render. Bans frozen poses.
tools: Read, Edit, Bash
---
1 `python engine/produce.py <ep> --stage compile`  2 `--stage sheet` (exit 2 prints UI-SAFE-ZONE VIOLATIONS)  3 Read ONLY contact_sheet.jpg.
Orange boxes = callouts inside ui_safe_zone, green boxes = faces. Fix by editing subject_zone / ui_safe_zone / camera preset / actor
positions - never Blender code. Check: faces never inside orange, eyes clean + bright, rim light separation, DoF only on OTS/CloseUp,
every actor has an action + emote + look (no frozen poses), group fully inside the frame. Recompile changed shots (`--shots s03`),
then `--stage render`. Skill: skill-camera-grammar.md
