---
description: Produce an episode end-to-end from a script
argument-hint: <episode_dir> [script]
---
Episode: $ARGUMENTS. 01-showrunner writes the shotlist from the script + catalog_manifest.json; run
`python engine/produce.py <dir> --stage voice`, fix durations, `--stage compile`, `--stage sheet`; 04-cinematographer reviews
contact_sheet.jpg and patches JSON; then `--stage render` (background) and `--stage final`; 05-motion-editor QA on 3 frames.
