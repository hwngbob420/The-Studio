# Character look-dev V2
Bases: Quaternius CC0 rigged humans (Poly Pizza) - suit_f, suit_m, worker_f, casual_m - all share one 62-bone rig.
engine/ingest_actor.py adds: eyeball spheres (iris+catch-light shader, blink/squint/wide keys, Eye bones for tracking), a viseme mouth card
(A-H,X + smile/frown), brow shape keys, V2 toon (cool shadow / neutral mid / warm highlight) and an ink hull whose vertex group EXCLUDES brows;
eyes and mouth have no ink. Variants swap skin/hair/eye colours, clothing palette by material name, height, accessories (glasses, mug).
Mixamo: see engine/ingest_mixamo.py (drop .fbx in asset_vault/mixamo_inbox).
