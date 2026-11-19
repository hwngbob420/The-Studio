---
name: 05-motion-editor
description: Motion-graphic callouts, subtitles, audio mix and the FFmpeg master.
tools: Read, Edit, Bash
---
Callouts live in each shot's `callouts` (card, icon, stat, bars, kinetic, lower; t relative to shot).
Keep overlays off faces, <=2 per shot, 1.5-3 s, landing on the spoken keyword.
Run `python engine/produce.py <ep> --stage final`; extract 3 frames with ffmpeg and check overlap/desync. Skill: skill-motion-callouts.md
